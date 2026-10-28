import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("order.errors")


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        details: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers


def request_id_of(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def error_content(request: Request, code: str, message: str, details: Any = None) -> dict:
    body: dict[str, Any] = {
        "error": {"code": code, "message": message},
        "request_id": request_id_of(request),
    }
    if details is not None:
        body["error"]["details"] = details
    return body


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_content(request, exc.code, exc.message, exc.details),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            {
                "location": ".".join(str(part) for part in error.get("loc", [])),
                "message": error.get("msg", "invalid value"),
                "type": error.get("type", "validation_error"),
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_content(
                request, "validation_error", "Request validation failed.", details
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(
            status_code=exc.status_code,
            content=error_content(request, f"http_{exc.status_code}", message),
            headers=exc.headers,
        )

    @app.exception_handler(SQLAlchemyError)
    async def handle_database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.error(
            "database_error",
            extra={"request_id": request_id_of(request), "error_type": type(exc).__name__},
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content=error_content(
                request, "internal_error", "An internal database error occurred."
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "unhandled_exception",
            extra={"request_id": request_id_of(request), "error_type": type(exc).__name__},
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content=error_content(
                request, "internal_error", "An unexpected internal error occurred."
            ),
        )
