# Docker Compose Topology

## Service Graph

```
                  trading-network (bridge)
     ┌──────────────────┼──────────────────────┐
     |                  |                       |
  postgres:5432    redis:6379              prometheus:9090
     |                  |                       |
     +--------+---------+                  grafana:3001
              |
     +--------+---------+
     |                  |
  api:8000      trading-engine:8081
     |
  web-ui:3000
```

All services share `trading-network`. No service exposes ports to the host except through explicit `ports:` mappings.

## Port Map

| Service | Internal | Host | Purpose |
|---|---|---|---|
| PostgreSQL | 5432 | 5432 | Database (dev access) |
| Redis | 6379 | 6379 | Cache/pubsub (dev access) |
| API | 8000 | 8000 | REST + WebSocket |
| Engine | 8081 | — | Health/metrics (internal only) |
| Web UI | 3000 | 3000 | Frontend |
| Prometheus | 9090 | 9090 | Metrics UI + API |
| Grafana | 3000 | 3001 | Dashboards |

In production, Traefik sits in front and only exposes 80/443. All other ports are internal.

## Health Checks & Dependencies

```
postgres (healthcheck: pg_isready)
  └── api (depends_on: postgres healthy)
  └── trading-engine (depends_on: postgres healthy)

redis (healthcheck: redis-cli ping)
  └── api (depends_on: redis healthy)
  └── trading-engine (depends_on: redis healthy)

api ──> prometheus (depends_on: api)
trading-engine ──> prometheus (depends_on: trading-engine)
prometheus ──> grafana (depends_on: prometheus)
```

Services wait for dependencies to be healthy before starting. This prevents "connection refused" errors during cold starts.

## Volumes

| Volume | Service | Purpose |
|---|---|---|
| `postgres_data` | postgres | Database files (persistent) |
| `redis_data` | redis | AOF persistence |
| `cache_data` | engine | Market data cache |
| `prometheus_data` | prometheus | 30-day metric retention |
| `grafana_data` | grafana | Dashboard configs, plugins |

## Resource Limits

| Service | CPU limit | Memory limit |
|---|---|---|
| API | 1 core | 512MB |
| Engine | 1 core | 512MB |
| Web UI | 0.5 core | 256MB |

Set via `deploy.resources` in compose. Prevents runaway processes from consuming the host.

## Deep Dive

- Docker Compose reference: https://docs.docker.com/compose/compose-file/
- Networking in Compose: https://docs.docker.com/compose/networking/
- Traefik docs: https://doc.traefik.io/traefik/
