# Observability

## Design Principle: Business vs Operational Metrics

**Grafana** (operational) — system health, performance, security forensics. Consumed by operators/SRE.

**Web UI dashboard** (business) — P&L, win rate, portfolio value, user counts. Consumed by admins/users.

These are intentionally separated. Grafana metrics follow the RED method (Rate, Errors, Duration) and USE method (Utilization, Saturation, Errors). Business metrics are computed from database queries in the API service.

## Prometheus Metrics

### API Service (`/metrics` on port 8000)

#### HTTP — RED Method

| Metric | Type | Labels | Rationale |
|---|---|---|---|
| `http_requests_total` | counter | method, endpoint, status_code | Request rate + status distribution. The foundation of all HTTP monitoring. |
| `http_request_duration_seconds` | histogram | method, endpoint | Latency percentiles (p50/p95/p99). Detects degradation before users complain. |
| `http_request_size_bytes` | histogram | endpoint | Spot abnormally large payloads (potential abuse). |

#### Authentication & Security

| Metric | Type | Labels | Rationale |
|---|---|---|---|
| `auth_attempts_total` | counter | status, client_ip | Spike in failures from one IP = brute-force attack. |
| `auth_token_refreshes_total` | counter | status | Tracks token lifecycle health. High failure rate = expired sessions or token theft. |
| `rate_limit_rejections_total` | counter | endpoint, client_ip | Visibility into rate limiter effectiveness. |
| `http_requests_by_ip_total` | counter | client_ip, method, endpoint | Forensic correlation for security incidents. High-cardinality — set retention policy. |

#### WebSocket

| Metric | Type | Labels | Rationale |
|---|---|---|---|
| `ws_connections_active` | gauge | — | Live connection count. Correlate with memory/CPU usage. |
| `ws_messages_forwarded_total` | counter | event_type | Event throughput. Detects Redis->WS pipeline stalls. |

#### Infrastructure

| Metric | Type | Labels | Rationale |
|---|---|---|---|
| `redis_connection_up` | gauge | — | 0/1 availability. Alerts when Redis is down. |
| `db_pool_active_connections` | gauge | — | Connection pool saturation. Approaching max = need to scale. |
| `db_pool_size` | gauge | — | Pool capacity for context. |

#### Credential Operations

| Metric | Type | Labels | Rationale |
|---|---|---|---|
| `credential_decryptions_total` | counter | broker_type | Tracks Fernet key usage. Unexpected spikes = suspicious activity. |

### Trading Engine (`/metrics` on port 8081)

#### Bot Fleet Health

| Metric | Type | Labels | Rationale |
|---|---|---|---|
| `engine_bots_total` | gauge | state | Fleet overview: running, paused, stopped, faulty. |
| `engine_heartbeat_age_seconds` | gauge | bot_name | How long since last heartbeat. Stale = stuck or crashed. |
| `engine_evaluation_cycles_total` | counter | bot_name | Proves the bot is actually doing work (not just "running"). |
| `engine_broker_errors_total` | counter | bot_name, error_type | Broker API failures. Consecutive errors trigger faulty state. |
| `engine_trades_executed_total` | counter | bot_name, broker | Trade throughput per bot. |

#### Process (auto-exposed by prometheus_client)

- `process_cpu_seconds_total`
- `process_resident_memory_bytes`
- `process_open_fds`

## Faulty Bot Definition

A bot is marked **faulty** when any of these conditions is true:

1. **Heartbeat timeout** — no heartbeat for > 2x the expected interval
2. **Consecutive broker errors** — 5+ failed broker API calls in a row
3. **Unrecovered exception** — evaluation loop caught an unhandled error and couldn't restart
4. **Stale during market hours** — "running" but 0 evaluation cycles during active trading hours

Faulty is distinct from **stopped** (intentional) and **paused** (user action). A faulty bot requires operator investigation.

## Grafana Dashboards

### Recommended Panels

**API Overview:**
- Request rate by endpoint (stacked area)
- p95 latency by endpoint (line)
- Error rate (4xx/5xx) over time
- Active WebSocket connections (gauge)

**Security:**
- Failed login attempts by IP (table, sorted by count)
- Rate limit rejections over time
- Request volume by IP (top 10)

**Trading Engine:**
- Bot fleet status (stat panel: running/paused/stopped/faulty)
- Heartbeat staleness per bot (bar gauge)
- Evaluation cycles/min per bot (line)
- Broker error rate (line)

**Infrastructure:**
- DB connection pool utilization
- Redis connection status
- Process memory/CPU per service

## Alerting Rules (Recommended)

| Alert | Condition | Severity |
|---|---|---|
| `HighAuthFailureRate` | > 10 failed logins/min from single IP | warning |
| `BotFaulty` | `engine_bots_total{state="faulty"} > 0` | critical |
| `BotHeartbeatStale` | `engine_heartbeat_age_seconds > 120` | warning |
| `APIHighLatency` | `p95(http_request_duration_seconds) > 2s` | warning |
| `RedisDown` | `redis_connection_up == 0` | critical |
| `DBPoolSaturated` | `db_pool_active_connections / db_pool_size > 0.8` | warning |
