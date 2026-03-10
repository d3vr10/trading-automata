"""Lightweight health/status HTTP server for the trading engine.

Runs on port 8081 (internal only) and exposes:
  GET /health   — liveness check
  GET /status   — JSON bot statuses
  GET /metrics  — Prometheus metrics
"""

import json
import logging
from typing import TYPE_CHECKING

from aiohttp import web
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from trading_automata.monitoring.logger import get_logger

if TYPE_CHECKING:
    from trading_automata.orchestration.orchestrator import BotOrchestrator

logger = get_logger(__name__)

_orchestrator: "BotOrchestrator | None" = None


async def _health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "trading-engine"})


async def _status(request: web.Request) -> web.Response:
    if _orchestrator is None:
        return web.json_response({"bots": {}})
    data = _orchestrator.get_bot_status()
    return web.json_response({"bots": data}, dumps=lambda o: json.dumps(o, default=str))


async def _metrics(request: web.Request) -> web.Response:
    return web.Response(
        body=generate_latest(),
        content_type="text/plain",
        charset="utf-8",
    )


def create_health_app(orchestrator: "BotOrchestrator") -> web.Application:
    """Create the aiohttp app wired to a running orchestrator."""
    global _orchestrator
    _orchestrator = orchestrator

    app = web.Application()
    app.router.add_get("/health", _health)
    app.router.add_get("/status", _status)
    app.router.add_get("/metrics", _metrics)
    return app


async def start_health_server(orchestrator: "BotOrchestrator", port: int = 8081) -> web.AppRunner:
    """Start the health HTTP server as a background task.

    Returns the runner so the caller can clean it up.
    """
    app = create_health_app(orchestrator)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health API listening on port {port}")
    return runner
