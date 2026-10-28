import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import products, reservations, system
from .config import Settings, get_settings
from .database import Database
from .errors import install_exception_handlers
from .logging_setup import setup_logging
from .metrics import InventoryMetrics
from .middleware import MaxBodySizeMiddleware, RateLimitMiddleware, RequestContextMiddleware
from .seed import seed_products

logger = logging.getLogger("inventory.app")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.app_name, settings.environment, settings.log_level)

    metrics = InventoryMetrics()
    database = Database(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        connect_timeout_seconds=settings.db_connect_timeout_seconds,
        statement_timeout_ms=settings.db_statement_timeout_ms,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info(
            "service_starting",
            extra={
                "environment": settings.environment,
                "version": settings.app_version,
            },
        )
        if settings.seed_on_start:
            try:
                seed_products(database, settings)
            except Exception:
                logger.exception("seed_failed")
        yield
        database.dispose()
        logger.info("service_stopped")

    app = FastAPI(
        title="Forge Commerce Inventory Service",
        description=(
            "Internal product catalog and inventory reservation API. "
            "This service is not intended to be exposed directly to the public frontend."
        ),
        version=settings.app_version,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.db = database
    app.state.metrics = metrics

    install_exception_handlers(app)
    app.include_router(system.router)
    app.include_router(products.router)
    app.include_router(reservations.router)

    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type", "X-Request-ID"],
            expose_headers=["X-Request-ID"],
            max_age=600,
        )

    app.add_middleware(MaxBodySizeMiddleware, max_bytes=settings.max_request_bytes)
    app.add_middleware(RateLimitMiddleware, limit_per_minute=settings.rate_limit_per_minute)
    app.add_middleware(
        RequestContextMiddleware,
        metrics=metrics,
        environment=settings.environment,
    )
    return app


app = create_app()
