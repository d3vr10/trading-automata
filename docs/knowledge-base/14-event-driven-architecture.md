# Event-Driven Architecture

## Core Idea

Instead of services calling each other synchronously (request/response), they communicate through **events** — messages that describe something that happened.

```
Synchronous:  API --HTTP POST--> Engine  (API blocks until Engine responds)
Event-driven: API --publish----> Redis ---subscribe--> Engine  (API continues immediately)
```

## Patterns Used in This Project

### Pub/Sub (Redis)

Publisher doesn't know who's listening. Subscriber doesn't know who published. They're decoupled through the channel name.

```
API publishes "pause_bot" to engine:commands
Engine subscribes to engine:commands, handles the message
Engine publishes "bot_status_changed" to engine:events
API's background task subscribes to engine:events, forwards to WebSocket
```

**Trade-off:** Messages are ephemeral. If nobody is listening, the message is lost. Fine for commands (user retries) and status events (next update overwrites). NOT fine for financial transactions (use a database).

### Event Sourcing (NOT used, but worth knowing)

Instead of storing current state, store every event that led to the current state. You can rebuild state by replaying events. We don't use this — trades are recorded as rows, not events. But it's the natural evolution if you need an audit trail.

## Key Concepts

**Eventual consistency:** After publishing an event, subscribers will *eventually* see it. There's a window where the API and Engine disagree about bot state. The system is designed to tolerate this — the database is the tiebreaker.

**Backpressure:** What happens when events arrive faster than you can process them? Redis pub/sub has no backpressure — slow subscribers just miss messages. Redis Streams (a possible upgrade) support consumer groups with acknowledgment.

**Idempotency:** Processing the same event twice should produce the same result. "Pause bot X" applied twice = bot X is paused. No harm done. This is essential when messages can be duplicated.

## When to Use What

| Pattern | Use when | Example |
|---|---|---|
| HTTP request/response | Caller needs immediate answer | Login, fetch trades |
| Pub/sub | Fire-and-forget notifications | Bot status changes |
| Message queue (with acks) | Messages must not be lost | Payment processing |
| Event sourcing | Need full audit trail | Financial ledger |

## Deep Dive

- Martin Fowler, *Event-Driven Architecture*: https://martinfowler.com/articles/201701-event-driven.html
- Chris Richardson, *Microservices Patterns* (Manning) — Chapters 3-4 on messaging
- Redis Streams: https://redis.io/docs/data-types/streams/
- Gregor Hohpe, *Enterprise Integration Patterns* — the complete taxonomy
