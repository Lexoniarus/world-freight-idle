"""Lightweight request tracing based on correlation IDs."""

from __future__ import annotations

import contextvars
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.requests import Request
from starlette.responses import Response

_TRACE_ID: contextvars.ContextVar[str] = contextvars.ContextVar(
    "trace_id",
    default="-",
)


def get_trace_id() -> str:
    """Return the correlation ID for the active request context."""
    return _TRACE_ID.get()


def new_trace_id() -> str:
    """Create a new opaque request correlation ID."""
    return uuid.uuid4().hex


class TraceIdMiddleware(BaseHTTPMiddleware):
    """Attach a trace ID to request context and response headers."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        trace_id = request.headers.get("X-Trace-Id") or new_trace_id()
        token = _TRACE_ID.set(trace_id)
        try:
            response = await call_next(request)
            response.headers["X-Trace-Id"] = trace_id
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = (
                "strict-origin-when-cross-origin"
            )
            return response
        finally:
            _TRACE_ID.reset(token)


@contextmanager
def background_trace(preparation_id: str) -> Iterator[None]:
    """Correlate one execution without retaining an HTTP request context."""
    token = _TRACE_ID.set(f"{preparation_id}:{new_trace_id()}")
    try:
        yield
    finally:
        _TRACE_ID.reset(token)
