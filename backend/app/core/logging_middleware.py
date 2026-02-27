"""Pure ASGI middleware: generates trace_id per request and logs request/response."""

import time
import uuid

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = structlog.get_logger(__name__)


class LoggingMiddleware:
    """ASGI middleware that assigns a trace_id and logs request/response timing.

    Uses the pure ASGI interface instead of BaseHTTPMiddleware to avoid
    issues with streaming responses and request body consumption.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        trace_id = str(uuid.uuid4())[:8]
        method = scope.get("method", "")
        path = scope.get("path", "")

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            trace_id=trace_id,
            method=method,
            path=path,
        )

        start = time.perf_counter()
        status_code = 0

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 0)
                headers: list[tuple[bytes, bytes]] = list(message.get("headers", []))
                headers.append((b"x-trace-id", trace_id.encode()))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            logger.exception("unhandled_exception")
            raise
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000)
            logger.info(
                "request_completed",
                status_code=status_code,
                duration_ms=duration_ms,
            )
