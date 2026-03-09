# Prometheus Metrics Design

## Two Methods, Two Services

### RED Method (API Service)

**R**ate, **E**rrors, **D**uration — the three things you need for any request-driven service.

| Metric | Type | What it tells you |
|---|---|---|
| `http_requests_total` | Counter | How many requests, by endpoint and status code |
| `http_request_duration_seconds` | Histogram | How long requests take (p50, p95, p99) |
| `http_request_size_bytes` | Histogram | Request payload sizes |

RED answers: "Is the API healthy?" If rate drops, errors spike, or latency increases — something is wrong.

### USE Method (Trading Engine)

**U**tilization, **S**aturation, **E**rrors — for resource-oriented services.

| Metric | Type | What it tells you |
|---|---|---|
| `engine_bots_total` | Gauge | Fleet composition (running/paused/stopped/faulty) |
| `engine_heartbeat_age_seconds` | Gauge | Is each bot actually doing work? |
| `engine_evaluation_cycles_total` | Counter | Throughput — how many cycles completed |
| `engine_broker_errors_total` | Counter | Broker reliability per bot |
| `engine_trades_executed_total` | Counter | Trade throughput |

## Metric Types

| Type | Behavior | Use when |
|---|---|---|
| **Counter** | Only goes up (resets on restart) | Counting events: requests, errors, trades |
| **Gauge** | Goes up and down | Current state: connections, pool size, temperature |
| **Histogram** | Counts values in configurable buckets | Distributions: latency, request size |

**Critical rule:** Never use a gauge for something that should be a counter. If you count errors with a gauge, a process restart resets it to 0 and you lose history. Counters survive this because `rate()` handles resets.

## Security Metrics

| Metric | Purpose |
|---|---|
| `auth_attempts_total{status,client_ip}` | Detect brute force (sort by failure + IP) |
| `rate_limit_rejections_total{endpoint,client_ip}` | Validate rate limiter is working |
| `http_requests_by_ip_total{client_ip}` | Forensic correlation during incidents |

**Cardinality warning:** `client_ip` labels create one time series per unique IP. With 30d retention this is manageable, but at scale you'd need to aggregate or use recording rules.

## Querying Basics

```promql
# Request rate (last 5 minutes)
rate(http_requests_total[5m])

# Error percentage
sum(rate(http_requests_total{status_code=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))

# 95th percentile latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Top 5 IPs by failed logins
topk(5, sum by (client_ip) (auth_attempts_total{status="failure"}))
```

## Deep Dive

- Prometheus docs: https://prometheus.io/docs/introduction/overview/
- RED method (Tom Wilkie): https://grafana.com/blog/2018/08/02/the-red-method-how-to-instrument-your-services/
- USE method (Brendan Gregg): https://www.brendangregg.com/usemethod.html
- PromQL tutorial: https://prometheus.io/docs/prometheus/latest/querying/basics/
