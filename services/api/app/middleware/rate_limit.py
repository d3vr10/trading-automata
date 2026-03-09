"""In-memory rate limiting middleware for auth endpoints.

Limits login/refresh attempts to prevent brute-force attacks.
Uses a simple sliding window counter per IP address.
"""

import time
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.metrics import rate_limit_rejections_total

# Rate limit: max requests per window
AUTH_RATE_LIMIT = 5  # requests
AUTH_WINDOW_SECONDS = 60  # per minute

# Paths subject to rate limiting
RATE_LIMITED_PATHS = {
    "/api/auth/login",
    "/api/auth/refresh",
}

# In-memory store: ip -> list of timestamps
_request_log: dict[str, list[float]] = defaultdict(list)


def _get_client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For behind a proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _cleanup_window(timestamps: list[float], now: float) -> list[float]:
    """Remove timestamps outside the current window."""
    cutoff = now - AUTH_WINDOW_SECONDS
    return [t for t in timestamps if t > cutoff]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate-limits authentication endpoints by client IP."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path not in RATE_LIMITED_PATHS:
            return await call_next(request)

        client_ip = _get_client_ip(request)
        now = time.monotonic()

        # Clean up old entries
        _request_log[client_ip] = _cleanup_window(_request_log[client_ip], now)

        if len(_request_log[client_ip]) >= AUTH_RATE_LIMIT:
            rate_limit_rejections_total.labels(
                endpoint=request.url.path, client_ip=client_ip,
            ).inc()
            retry_after = int(AUTH_WINDOW_SECONDS - (now - _request_log[client_ip][0]))
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Too many requests. Try again later."},
                headers={"Retry-After": str(max(retry_after, 1))},
            )

        _request_log[client_ip].append(now)
        return await call_next(request)
