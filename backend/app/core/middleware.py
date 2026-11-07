"""Request middleware: request IDs, access logging and HTTP metrics.

Implemented as plain ASGI middleware (not `BaseHTTPMiddleware`) so context variables propagate to
handlers and streaming responses are not buffered.
"""

from __future__ import annotations

import re
import time
import uuid

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.metrics import HTTP_LATENCY, HTTP_REQUESTS
from app.core.request_context import reset_request_id, set_request_id

REQUEST_ID_HEADER = "x-request-id"
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_UNLOGGED_PATHS = frozenset({"/metrics"})

log = structlog.get_logger("app.access")


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope.get("headers") or []).get(REQUEST_ID_HEADER.encode(), b"").decode()
        request_id = incoming if _VALID_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        token = set_request_id(request_id)
        structlog.contextvars.bind_contextvars(request_id=request_id)

        status_code = 500
        started = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers") or [])
                headers.append((REQUEST_ID_HEADER.encode(), request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed = time.perf_counter() - started
            route = getattr(scope.get("route"), "path", None) or "unmatched"
            method = scope.get("method", "")
            HTTP_REQUESTS.labels(method=method, route=route, status=str(status_code)).inc()
            HTTP_LATENCY.labels(method=method, route=route).observe(elapsed)
            if scope.get("path") not in _UNLOGGED_PATHS:
                log.info(
                    "http_request",
                    method=method,
                    route=route,
                    status=status_code,
                    duration_ms=round(elapsed * 1000, 2),
                )
            structlog.contextvars.clear_contextvars()
            reset_request_id(token)
