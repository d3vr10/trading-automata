# Observability Engineering

## The Three Pillars

| Pillar | What it is | Tool in this project |
|---|---|---|
| **Metrics** | Numeric measurements over time | Prometheus + Grafana |
| **Logs** | Timestamped text records of events | Python logging + Docker json-file |
| **Traces** | Request flow across services | Not implemented (future: OpenTelemetry) |

Metrics tell you *something is wrong*. Logs tell you *what went wrong*. Traces tell you *where it went wrong* across service boundaries.

## Why Metrics Alone Aren't Enough

A spike in `http_requests_total{status_code="500"}` tells you errors increased. But which user? Which request body? What was the stack trace? You need logs for that. And if the error originated in the engine but surfaced in the API, you need traces to connect them.

This project currently has metrics + logs. Traces are the natural next step (via OpenTelemetry).

## SLIs, SLOs, SLAs

| Term | Definition | Example |
|---|---|---|
| **SLI** (Service Level Indicator) | A measurable aspect of service quality | p95 latency, error rate, uptime |
| **SLO** (Service Level Objective) | Target value for an SLI | "p95 latency < 500ms", "error rate < 1%" |
| **SLA** (Service Level Agreement) | SLO + consequences for missing it | "99.9% uptime or we refund you" |

For an internal platform, you set SLOs without SLAs. They guide alerting thresholds and engineering priorities.

**Recommended SLOs for Trading Automata:**

| SLI | SLO | Rationale |
|---|---|---|
| API p95 latency | < 500ms | UI responsiveness |
| API error rate | < 1% | Reliability |
| Bot heartbeat freshness | < 2x poll interval | Trading continuity |
| Faulty bot count | = 0 | All bots should be healthy |

## The Four Golden Signals (Google SRE)

1. **Latency** — how long requests take (distinguish success from error latency)
2. **Traffic** — how much demand the system is receiving
3. **Errors** — rate of failed requests
4. **Saturation** — how full the system is (DB pool, memory, CPU)

These map directly to our Grafana dashboard's top row.

## Alerting Philosophy

- Alert on **symptoms** (high error rate), not causes (disk full)
- Use **severity levels**: critical (wake someone up), warning (look at it today)
- Every alert must have a **runbook** (even if it's just "check Grafana dashboard X")
- Delete alerts that nobody acts on — alert fatigue is worse than missing alerts

## Deep Dive

- Charity Majors, *Observability Engineering* (O'Reilly) — the modern take on monitoring
- Google SRE book, free online: https://sre.google/sre-book/table-of-contents/
- OpenTelemetry: https://opentelemetry.io/docs/
- Brendan Gregg, *Systems Performance* — Linux performance observability
