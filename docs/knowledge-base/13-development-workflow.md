# Development Workflow

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env with your API keys, JWT_SECRET, FERNET_KEY

# 2. Start infrastructure
cd docker
docker compose up -d postgres redis

# 3. Run migrations
cd ..
alembic -c shared/alembic.ini upgrade head

# 4. Start services (choose one)
# Option A: All via Docker
docker compose up -d

# Option B: Infrastructure in Docker, services locally (for debugging)
cd services/api && uvicorn app.main:app --reload --port 8000
cd services/trading-engine && python -m trading_automata.main
cd services/web-ui && npm run dev
```

## Debugging Tips

**API not connecting to DB?**
- Check `DATABASE_URL` in `.env` — must use `postgresql://` (not `postgres://`)
- Verify postgres is healthy: `docker compose ps` should show "healthy"
- Test connection: `docker compose exec postgres psql -U postgres -d trading-automata`

**Trading engine not connecting to Redis?**
- `REDIS_URL` must be set. Without it, engine runs in standalone mode (no API communication)
- Test: `docker compose exec redis redis-cli ping` should return `PONG`

**WebSocket not connecting?**
- Check browser console for the WS URL — must match `NEXT_PUBLIC_WS_URL`
- WS auth requires a valid access token as query param: `ws://localhost:8000/api/ws?token=...`

**Metrics endpoint empty?**
- Metrics only appear after the first request/cycle. Hit the API once, then check `/metrics`
- For engine: the health server must be running on port 8081

## Generating Secrets

```bash
# JWT secret (any random string, 32+ chars)
openssl rand -hex 32

# Fernet key (must be url-safe base64, exactly 32 bytes)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Running Tests

```bash
cd services/trading-engine
pytest                        # all tests
pytest tests/unit/            # unit only
pytest -x --tb=short          # stop on first failure
```

## Deep Dive

- Docker Compose CLI: https://docs.docker.com/compose/reference/
- uvicorn (ASGI server): https://www.uvicorn.org/
- pytest docs: https://docs.pytest.org/en/stable/
