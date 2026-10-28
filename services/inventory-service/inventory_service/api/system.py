import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

router = APIRouter(tags=["system"])
logger = logging.getLogger("inventory.system")


@router.get("/health")
def health(request: Request) -> dict:
    settings = request.app.state.settings
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


@router.get("/ready")
def ready(request: Request) -> JSONResponse:
    database = request.app.state.db
    try:
        database.check()
    except Exception:
        logger.warning("readiness_check_failed", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "checks": {"database": "unavailable"}},
        )
    return JSONResponse(content={"status": "ready", "checks": {"database": "ok"}})


@router.get("/metrics", include_in_schema=False)
def metrics(request: Request) -> Response:
    registry = request.app.state.metrics.registry
    return Response(content=generate_latest(registry), media_type=CONTENT_TYPE_LATEST)
