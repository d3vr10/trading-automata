# Grafana Dashboards

## Dashboard Structure

The `trading-automata.json` dashboard is organized in four rows, each answering a different operational question:

| Row | Question it answers |
|---|---|
| **API — HTTP Overview** | Is the API healthy? (rate, errors, latency, connections) |
| **Security & Auth** | Is anyone attacking us? (failed logins, rate limits, IP forensics) |
| **Trading Engine — Bot Fleet** | Are the bots working? (fleet state, heartbeats, cycles, errors, trades) |
| **Infrastructure** | Are the supporting systems healthy? (DB pool, WS messages, CPU, memory) |

## Panel Design Rationale

**Stat panels** (top row) — glanceable current values. You should be able to look at the top row and know in 2 seconds if anything needs attention.

**Time series panels** — trend analysis. Is the error rate increasing? Is latency degrading? Trends matter more than absolute values.

**Tables** — forensic data. Top IPs by failed logins, top IPs by request volume. You look at these during an incident, not during normal operation.

**Bar gauges** — per-bot heartbeat staleness. Horizontal bars give an instant visual of which bot is falling behind.

## Importing the Dashboard

1. Open Grafana (port 3001)
2. Dashboards -> Import -> Upload JSON file
3. Select your Prometheus datasource from the dropdown
4. Click Import

The JSON uses `__inputs` for the datasource, so it works with ANY Prometheus instance — no hardcoded UIDs.

## Alert Rules (Recommended)

Set these up in Grafana Alerting after importing:

| Alert | Condition | Severity |
|---|---|---|
| High error rate | `error_rate > 5%` for 5min | Critical |
| High latency | `p95 > 2s` for 5min | Warning |
| Faulty bot | `engine_bots_total{state="faulty"} > 0` for 1min | Critical |
| Heartbeat stale | `engine_heartbeat_age_seconds > 120` for 2min | Warning |
| Failed logins spike | `rate(auth_attempts_total{status="failure"}) > 1/s` for 5min | Warning |
| Redis down | `redis_connection_up == 0` for 1min | Critical |

## Business vs Operational Metrics (Reminder)

This Grafana dashboard is for **operational** metrics only. Business metrics (P&L, win rate, portfolio value, user counts) belong in the **Web UI admin dashboard** — they're domain-specific and meaningful to non-engineers.

## Deep Dive

- Grafana dashboard best practices: https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/best-practices/
- Grafana alerting: https://grafana.com/docs/grafana/latest/alerting/
- Google SRE book, Chapter 6 (Monitoring): https://sre.google/sre-book/monitoring-distributed-systems/
