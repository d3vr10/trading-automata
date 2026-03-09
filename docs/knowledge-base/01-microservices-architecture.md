# Microservices Architecture

## Mental Model

Trading Automata is split into three services, each with a single responsibility:

```
                     +-------------+
    Browser -------->|   Web UI    |  NextJS 16 — renders UI, talks to API only
                     +------+------+
                            |
                        HTTP / WS
                            |
                     +------v------+
                     |     API     |  FastAPI — auth, CRUD, WebSocket relay
                     +------+------+
                            |
                    Redis pub/sub + shared PostgreSQL
                            |
                     +------v------+
                     |   Engine    |  Python — bot orchestration, broker calls
                     +-------------+
```

**Why this split?**
- The trading engine runs long-lived loops (minutes between iterations). The API handles short-lived HTTP requests (milliseconds). Mixing these in one process means a slow broker call blocks API responses.
- The web UI is a static frontend — it has no business accessing the database or Redis directly. Everything goes through the API.
- Each service scales independently. You can run multiple API replicas behind a load balancer without duplicating trading engine state.

## Key Principle: Shared Nothing (Almost)

Services share only two things:
1. **PostgreSQL** — the source of truth for trades, users, sessions
2. **Redis** — ephemeral commands and events (not state)

Everything else is isolated. The engine has its own broker connections, its own config files, its own health server.

## Where Things Live

| Concern | Service | Why there |
|---|---|---|
| JWT issuance / validation | API | Auth is an API concern |
| Broker API calls | Engine | Long-lived, stateful connections |
| Trade recording | Engine writes, API reads | Engine is the authority on what happened |
| Bot commands (pause/resume) | API sends, Engine executes | API is the user-facing surface |
| WebSocket to browser | API | Browsers connect to the API, not the engine |

## Deep Dive

- Sam Newman, *Building Microservices* (O'Reilly) — the canonical reference
- Martin Fowler's [Microservices Resource Guide](https://martinfowler.com/microservices/)
- For when NOT to use microservices: [MonolithFirst](https://martinfowler.com/bliki/MonolithFirst.html)
