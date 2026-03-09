# Faulty Bot Detection

## The Problem

A bot can be in several states: running, paused, stopped. But there's a fourth state that's harder to detect: **running but broken**. The process is alive, the loop is iterating, but it's not actually trading because something is silently wrong.

## The Four Conditions

A bot is marked **faulty** when ANY of these are true:

### 1. Heartbeat Timeout

```
Condition: time_since_last_heartbeat > 2 * poll_interval
```

The bot updates `_last_heartbeat` at the end of each evaluation cycle. If the heartbeat goes stale, the loop is stuck — probably waiting on a hung broker call, a deadlock, or an infinite loop in a strategy.

**Why 2x?** One missed cycle could be normal jitter (GC pause, network blip). Two consecutive misses indicates a real problem.

### 2. Consecutive Broker Errors (>= 5)

```
Condition: _consecutive_broker_errors >= 5
```

The counter increments on every failed broker reconnection attempt and resets to 0 on a successful evaluation cycle. Five consecutive failures means the broker is down or credentials are invalid.

**Why 5?** Broker APIs have transient failures (rate limits, maintenance windows). Five consecutive failures filters out transients while catching real outages quickly.

### 3. Unrecovered Exception

If the trading loop exits due to an uncaught exception, the bot enters stopped state. The orchestrator detects this via the heartbeat going stale (condition 1).

### 4. Stale During Market Hours (Future)

Not yet implemented. Would check if a bot is running but hasn't produced any signals during market hours when its symbols are actively trading. This catches scenarios where the data provider returns stale bars.

## How It Surfaces

1. **Prometheus gauge:** `engine_bots_total{state="faulty"}` — triggers alerts
2. **Status API:** `/status` endpoint includes `faulty: true` and `faulty_reason`
3. **Web UI:** Bot detail page shows faulty state with reason

## Deep Dive

- Health check patterns: https://microservices.io/patterns/observability/health-check-api.html
- Circuit breaker (related pattern): https://martinfowler.com/bliki/CircuitBreaker.html
