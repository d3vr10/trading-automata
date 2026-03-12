"""FastAPI application entry point with lifespan management."""

import asyncio
import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.routing import Route

from app.auth.bootstrap import bootstrap_root_user
from app.config import settings
from app.database import async_session, engine
from app.metrics import (
    PrometheusMiddleware, metrics_endpoint,
    redis_connection_up, db_pool_active_connections, db_pool_size,
)
from app.middleware.rate_limit import RateLimitMiddleware
from app.routers import auth, users, bots, credentials, trades, strategies, ws, notifications

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # Startup
    logger.info("Trading Automata API starting up...")

    # Connect Redis
    redis_client = aioredis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=5,
    )
    try:
        await redis_client.ping()
        logger.info("Redis connected")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}")
        redis_client = None

    app.state.redis = redis_client

    # Override Redis dependency for bots router
    if redis_client:
        async def _get_redis():
            return redis_client
        app.dependency_overrides[bots.get_redis] = _get_redis

    # Start Redis event listener for WebSocket forwarding
    redis_listener_task = None
    snapshot_task = None
    if redis_client:
        redis_listener_task = asyncio.create_task(ws.redis_event_listener(redis_client))
        logger.info("Redis→WebSocket event listener started")
        from app.services.bot_service import portfolio_snapshot_loop
        snapshot_task = asyncio.create_task(
            portfolio_snapshot_loop(redis_client, async_session, interval_seconds=3600)
        )
        logger.info("Portfolio snapshot persistence task started (hourly)")

    # Bootstrap root user
    async with async_session() as session:
        await bootstrap_root_user(session)

    # Set initial infrastructure metrics
    redis_connection_up.set(1 if redis_client else 0)
    pool = engine.pool
    db_pool_size.set(pool.size())

    logger.info("API service ready")

    yield

    # Shutdown
    logger.info("API service shutting down...")
    for task in [redis_listener_task, snapshot_task]:
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    if redis_client:
        await redis_client.close()
    await engine.dispose()
    logger.info("Cleanup complete")


app = FastAPI(
    title="Trading Automata API",
    version="0.5.0",
    description="Multi-account trading platform API",
    lifespan=lifespan,
)

# Prometheus metrics (outermost = first to process)
app.add_middleware(PrometheusMiddleware)

# Rate limiting on auth endpoints (5 req/min/IP)
app.add_middleware(RateLimitMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(bots.router)
app.include_router(credentials.router)
app.include_router(trades.router)
app.include_router(strategies.router)
app.include_router(notifications.router)
app.include_router(ws.router)

# Prometheus /metrics endpoint
app.routes.append(Route("/metrics", metrics_endpoint))


@app.get("/api/health")
async def health_check():
    """API service health check."""
    return {"status": "ok", "service": "api"}
