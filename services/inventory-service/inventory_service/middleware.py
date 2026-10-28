import asyncio
import json
import logging
import math
import re
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .metrics import InventoryMetrics

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{8,128}$")
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        *,
        metrics: InventoryMetrics,
        environment: str,
    ) -> None:
        super().__init__(app)
        self.metrics = metrics
        self.environment = environment
        self.logger = logging.getLogger("inventory.http")

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("x-request-id", "")
        if not REQUEST_ID_PATTERN.fullmatch(request_id):
            request_id = uuid.uuid4().hex
        request.state.request_id = request_id

        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            duration = time.perf_counter() - started
            self.metrics.observe_http(
                method=request.method,
                route="unhandled",
                status=500,
                duration_seconds=duration,
            )
            self.logger.exception(
                "http_request_failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "route": "unhandled",
                    "status_code": 500,
                    "duration_ms": round(duration * 1000, 2),
                    "environment": self.environment,
                },
            )
            raise

        duration = time.perf_counter() - started
        route = getattr(request.scope.get("route"), "path", None) or "unmatched"
        self.metrics.observe_http(
            method=request.method,
            route=route,
            status=status_code,
            duration_seconds=duration,
        )
        log_method = self.logger.error if status_code >= 500 else self.logger.info
        log_method(
            "http_request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "route": route,
                "status_code": status_code,
                "duration_ms": round(duration * 1000, 2),
                "environment": self.environment,
            },
        )

        response.headers["X-Request-ID"] = request_id
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response


class MaxBodySizeMiddleware:
    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") not in {"POST", "PUT", "PATCH"}:
            await self.app(scope, receive, send)
            return

        messages: list[Message] = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            total += len(message.get("body", b""))
            if total > self.max_bytes:
                request_id = scope.get("state", {}).get("request_id", "unknown")
                body = json.dumps(
                    {
                        "error": {
                            "code": "request_too_large",
                            "message": f"Request body exceeds {self.max_bytes} bytes.",
                        },
                        "request_id": request_id,
                    }
                ).encode("utf-8")
                await send(
                    {
                        "type": "http.response.start",
                        "status": 413,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"content-length", str(len(body)).encode("ascii")),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": body})
                return
            messages.append(message)
            if not message.get("more_body", False):
                break

        index = 0

        async def replay() -> Message:
            nonlocal index
            if index < len(messages):
                message = messages[index]
                index += 1
                return message
            return {"type": "http.disconnect"}

        await self.app(scope, replay, send)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, limit_per_minute: int) -> None:
        super().__init__(app)
        self.limit = limit_per_minute
        self.window_seconds = 60.0
        self._windows: dict[str, tuple[float, int]] = {}
        self._lock = asyncio.Lock()

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if self.limit <= 0 or not request.url.path.startswith("/api/"):
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        now = time.monotonic()
        async with self._lock:
            if len(self._windows) > 50_000:
                self._windows.clear()
            window_start, count = self._windows.get(client, (now, 0))
            if now - window_start >= self.window_seconds:
                window_start, count = now, 0
            count += 1
            self._windows[client] = (window_start, count)

        remaining = max(self.limit - count, 0)
        if count > self.limit:
            retry_after = max(1, math.ceil(self.window_seconds - (now - window_start)))
            response = JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "rate_limited",
                        "message": "Too many requests. Retry later.",
                    },
                    "request_id": getattr(request.state, "request_id", "unknown"),
                },
                headers={"Retry-After": str(retry_after)},
            )
            response.headers["X-RateLimit-Limit"] = str(self.limit)
            response.headers["X-RateLimit-Remaining"] = "0"
            return response

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
