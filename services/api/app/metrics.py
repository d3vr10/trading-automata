"""Prometheus metrics for the API service.

Follows RED method (Rate, Errors, Duration) for HTTP endpoints
and USE method (Utilization, Saturation, Errors) for infrastructure.
"""

from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.requests import Request
from starlette.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
import time


# ──────────────────────────────────────────────
# HTTP — RED Method
# ──────────────────────────────────────────────

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

http_request_size_bytes = Histogram(
    "http_request_size_bytes",
    "HTTP request body size in bytes",
    ["endpoint"],
    buckets=(100, 500, 1000, 5000, 10000, 50000, 100000),
)

# ──────────────────────────────────────────────
# Authentication & Security
# ──────────────────────────────────────────────

auth_attempts_total = Counter(
    "auth_attempts_total",
    "Authentication attempts",
    ["status", "client_ip"],
)

auth_token_refreshes_total = Counter(
    "auth_token_refreshes_total",
    "Token refresh attempts",
    ["status"],
)

rate_limit_rejections_total = Counter(
    "rate_limit_rejections_total",
    "Rate limit rejections",
    ["endpoint", "client_ip"],
)

http_requests_by_ip_total = Counter(
    "http_requests_by_ip_total",
    "HTTP requests by client IP (security forensics)",
    ["client_ip", "method", "endpoint"],
)

# ──────────────────────────────────────────────
# WebSocket
# ──────────────────────────────────────────────

ws_connections_active = Gauge(
    "ws_connections_active",
    "Active WebSocket connections",
)

ws_messages_forwarded_total = Counter(
    "ws_messages_forwarded_total",
    "WebSocket messages forwarded to clients",
    ["event_type"],
)

# ──────────────────────────────────────────────
# Infrastructure
# ──────────────────────────────────────────────

redis_connection_up = Gauge(
    "redis_connection_up",
    "Redis connection status (1=up, 0=down)",
)

db_pool_active_connections = Gauge(
    "db_pool_active_connections",
    "Active database connections in pool",
)

db_pool_size = Gauge(
    "db_pool_size",
    "Database connection pool size",
)

# ──────────────────────────────────────────────
# Credential Operations
# ──────────────────────────────────────────────

credential_decryptions_total = Counter(
    "credential_decryptions_total",
    "Credential decryption operations",
    ["broker_type"],
)


def _normalize_path(path: str) -> str:
    """Normalize URL path to reduce cardinality.

    Replaces numeric IDs and UUIDs with placeholders.
    """
    parts = path.rstrip("/").split("/")
    normalized = []
    for part in parts:
        if part.isdigit():
            normalized.append("{id}")
        elif len(part) == 36 and part.count("-") == 4:
            normalized.append("{uuid}")
        else:
            normalized.append(part)
    return "/".join(normalized)


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware that records HTTP RED metrics and per-IP tracking."""

    async def dispatch(self, request: Request, call_next):
        # Skip metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        path = _normalize_path(request.url.path)
        client_ip = _get_client_ip(request)

        # Record request size
        content_length = request.headers.get("content-length")
        if content_length and content_length.isdigit():
            http_request_size_bytes.labels(endpoint=path).observe(int(content_length))

        # Per-IP tracking (security forensics)
        http_requests_by_ip_total.labels(
            client_ip=client_ip, method=method, endpoint=path,
        ).inc()

        # Time the request
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        status_code = str(response.status_code)

        http_requests_total.labels(
            method=method, endpoint=path, status_code=status_code,
        ).inc()
        http_request_duration_seconds.labels(
            method=method, endpoint=path,
        ).observe(duration)

        return response


async def metrics_endpoint(request: Request) -> Response:
    """Expose Prometheus metrics at /metrics."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
