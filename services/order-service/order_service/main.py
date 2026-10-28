import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import catalog, orders, storefront, system
from .client import InventoryClient
from .config import Settings, get_settings
from .database import Database
from .errors import install_exception_handlers
from .logging_setup import setup_logging
from .metrics import OrderMetrics
from .middleware import MaxBodySizeMiddleware, RateLimitMiddleware, RequestContextMiddleware
from .workflow import expire_due_orders

logger = logging.getLogger("order.app")


def create_app(
    settings: Settings | None = None,
    inventory_client: InventoryClient | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.app_name, settings.environment, settings.log_level)

    metrics = OrderMetrics()
    database = Database(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        connect_timeout_seconds=settings.db_connect_timeout_seconds,
        statement_timeout_ms=settings.db_statement_timeout_ms,
    )
    client = inventory_client or InventoryClient(
        base_url=settings.inventory_base_url,
        timeout_seconds=settings.inventory_timeout_seconds,
        metrics=metrics,
    )

    async def checkout_expiry_worker() -> None:
        while True:
            try:
                expired = await expire_due_orders(
                    database,
                    client,
                    batch_size=settings.checkout_expiry_batch_size,
                )
                if expired:
                    metrics.expired_orders.inc(expired)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("checkout_expiry_sweep_failed")
            await asyncio.sleep(settings.checkout_expiry_sweep_seconds)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info(
            "service_starting",
            extra={
                "environment": settings.environment,
                "version": settings.app_version,
                "inventory_base_url": settings.inventory_base_url,
            },
        )
        expiry_task = (
            asyncio.create_task(checkout_expiry_worker())
            if settings.checkout_expiry_enabled
            else None
        )
        yield
        if expiry_task is not None:
            expiry_task.cancel()
            with suppress(asyncio.CancelledError):
                await expiry_task
        await client.aclose()
        database.dispose()
        logger.info("service_stopped")

    app = FastAPI(
        title="Forge Commerce Order Service",
        description=(
            "Public commerce API for orders and the product catalog proxy. "
            "Inventory is owned by the internal inventory service."
        ),
        version=settings.app_version,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.db = database
    app.state.metrics = metrics
    app.state.inventory_client = client

    install_exception_handlers(app)
    app.include_router(system.router)
    app.include_router(orders.router)
    app.include_router(storefront.router)
    app.include_router(catalog.router)

    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type", "Idempotency-Key", "X-Request-ID"],
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
