"""Prometheus metrics for the trading engine.

Exposes bot fleet health metrics via the /metrics endpoint on port 8081.
"""

from prometheus_client import Counter, Gauge


# ──────────────────────────────────────────────
# Bot Fleet Health
# ──────────────────────────────────────────────

engine_bots_total = Gauge(
    "engine_bots_total",
    "Number of bots by state",
    ["state"],  # running, paused, stopped, faulty
)

engine_heartbeat_age_seconds = Gauge(
    "engine_heartbeat_age_seconds",
    "Seconds since last heartbeat per bot",
    ["bot_name"],
)

engine_evaluation_cycles_total = Counter(
    "engine_evaluation_cycles_total",
    "Total evaluation cycles completed per bot",
    ["bot_name"],
)

engine_broker_errors_total = Counter(
    "engine_broker_errors_total",
    "Broker API errors per bot",
    ["bot_name", "error_type"],
)

engine_trades_executed_total = Counter(
    "engine_trades_executed_total",
    "Trades executed per bot",
    ["bot_name", "broker"],
)
