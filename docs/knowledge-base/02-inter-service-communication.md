# Inter-Service Communication

## The Two Channels

| Channel | Direction | Purpose |
|---|---|---|
| `engine:commands` | API -> Engine | User actions: pause, resume, stop, get_status |
| `engine:events` | Engine -> API | State changes: bot_status_changed, trade_executed |

Both use **Redis pub/sub** — fire-and-forget messaging. If a subscriber is offline when a message is published, that message is lost. This is acceptable because:
- Commands are user-initiated and can be retried
- Events are supplementary (the database is the real source of truth)

## Message Contract

Commands follow request/response over pub/sub:
```json
{
  "command": "pause_bot",
  "data": { "bot_name": "sigma-alpha", "user_id": 1 },
  "request_id": "uuid"
}
```

Events are broadcast:
```json
{
  "event_type": "bot_status_changed",
  "data": { "bot_name": "sigma-alpha", "status": "paused" },
  "user_id": 1,
  "timestamp": "2026-03-07T12:00:00Z"
}
```

## Status Polling (Fallback)

The engine also writes to `engine:status` (a Redis hash) on every metrics loop iteration (every 15s). The API can poll this as a fallback when it needs current state without waiting for an event.

## Why Not HTTP Between Services?

The engine doesn't expose an HTTP API to the network (only port 8081 for health/metrics, internal only). Redis pub/sub is:
- Non-blocking for the engine (publish and continue)
- Naturally async (the engine doesn't wait for the API to acknowledge)
- Already in the stack (we need Redis for caching anyway)

## Deep Dive

- Redis pub/sub docs: https://redis.io/docs/manual/pubsub/
- For durable messaging (if you outgrow pub/sub): Redis Streams, NATS, or RabbitMQ
- Enterprise Integration Patterns (Hohpe & Woolf) — the bible of messaging patterns
