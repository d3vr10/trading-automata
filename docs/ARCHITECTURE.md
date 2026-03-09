# System Architecture

## Services

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Web UI    │────>│     API     │<───>│   Trading   │
│  (NextJS)   │     │  (FastAPI)  │     │   Engine    │
│  port 3000  │     │  port 8000  │     │  (Python)   │
└─────────────┘     └──────┬──────┘     └──────┬──────┘
                           │                    │
                    ┌──────┴──────┐      ┌──────┴──────┐
                    │ PostgreSQL  │      │    Redis    │
                    │  port 5432  │      │  port 6379  │
                    └─────────────┘      └─────────────┘
                                         ┌─────────────┐
                    ┌─────────────┐      │   Grafana   │
                    │ Prometheus  │─────>│  port 3001  │
                    │  port 9090  │      └─────────────┘
                    └─────────────┘
```

### Trading Engine (`services/trading-engine/`)

Bot orchestration, broker SDKs, strategy execution. Runs as a long-lived process.

- **Orchestrator**: manages bot lifecycle (start, pause, resume, stop)
- **Brokers**: Alpaca, Coinbase adapters
- **Strategies**: pluggable via registry (sigma series, momentum, mean reversion, etc.)
- **Redis integration**: listens on `engine:commands`, publishes to `engine:events`, writes to `engine:status` hash
- **Health API**: aiohttp on port 8081 (`/health`, `/status`, `/metrics`)

### API Service (`services/api/`)

FastAPI backend for auth, CRUD, and real-time event forwarding.

- **Auth**: JWT (HS256), bcrypt passwords, httponly refresh cookies
- **RBAC**: root > admin > user
- **Broker credentials**: Fernet-encrypted at rest
- **WebSocket**: `/api/ws?token=<jwt>` — forwards Redis events filtered by user_id
- **Rate limiting**: 5 req/min/IP on auth endpoints
- **Prometheus**: `/metrics` endpoint with RED metrics, auth counters, security tracking

### Web UI (`services/web-ui/`)

NextJS 16 with React 19, shadcn/ui, Tailwind v4.

- Communicates with API only via HTTP/WebSocket (no direct DB access)
- Auth middleware redirects unauthenticated users to `/login`
- Dark purple glassmorphism theme
- Can be extracted to a separate repository with zero code changes

## Inter-Service Communication

| Channel | Direction | Purpose |
|---|---|---|
| `engine:commands` (Redis pub/sub) | API -> Engine | Bot lifecycle commands (pause, resume, stop) |
| `engine:events` (Redis pub/sub) | Engine -> API | Trade executions, signal generation, status changes |
| `engine:status` (Redis hash) | Engine -> API | Bot status polling (running, paused, allocation, balance) |
| PostgreSQL | Shared | Trades, positions, users, credentials, metrics |

## Authentication Flow

1. `POST /api/auth/login` — returns JWT access token + sets httponly refresh cookie
2. Access token (30min) sent as `Authorization: Bearer <token>`
3. On 401, frontend calls `POST /api/auth/refresh` using the cookie
4. WebSocket auth: JWT passed as query param `?token=<jwt>`

## Database Schema

Managed by Alembic migrations in `shared/alembic/versions/`:

- `001` — Initial schema (trades, positions, events, health_checks, metrics, bot_sessions)
- `002` — Bot sessions
- `003` — Bot name field
- `004` — Users, broker_credentials, password_reset_tokens, user_settings
- `005` — user_id foreign key on all trading tables

## Config Priority

Highest to lowest: **CLI args > environment variables > config.yml > defaults**
