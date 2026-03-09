# Trading Automata — Knowledge Map

A structured learning path to build a complete mental model of the platform. Start at Tier 1 and work down — each tier assumes understanding of the previous.

---

## Tier 1: Architecture & System Design

The foundation. Without this, nothing else makes sense.

1. [[01-microservices-architecture]] — What runs where, why it's split this way, how services talk
2. [[02-inter-service-communication]] — Redis pub/sub, channels, message contracts
3. [[03-database-schema]] — Tables, relationships, multi-tenancy model
4. [[04-authentication-and-rbac]] — JWT flow, role hierarchy, credential encryption

## Tier 2: Trading Domain

The business logic. This is what the platform actually *does*.

5. [[05-trading-loop-lifecycle]] — How a bot goes from config to executing trades
6. [[06-strategies-and-signals]] — Strategy interface, signal flow, registry pattern
7. [[07-portfolio-and-risk-management]] — Virtual fences, allocation types, position sizing
8. [[08-broker-abstraction]] — Broker interface, Alpaca/Coinbase specifics, rate limits

## Tier 3: Observability & Operations

How you know the system is healthy and diagnose problems.

9. [[09-prometheus-metrics-design]] — RED/USE methods, metric types, what each metric tells you
10. [[10-faulty-bot-detection]] — The 4 conditions, why each matters, how it surfaces
11. [[11-grafana-dashboards]] — Dashboard structure, panel rationale, alert rules

## Tier 4: Infrastructure & Deployment

How the whole thing runs in production.

12. [[12-docker-compose-topology]] — Service graph, networking, volumes, resource limits
13. [[13-development-workflow]] — Local setup, running services, debugging tips

## Tier 5: Deepening Your Engineering Background

General concepts that apply beyond this project.

14. [[14-event-driven-architecture]] — Pub/sub patterns, eventual consistency, backpressure
15. [[15-observability-engineering]] — The three pillars, SLIs/SLOs, why metrics alone aren't enough
16. [[16-api-design-patterns]] — REST conventions, middleware chains, dependency injection

---

## Suggested Reading Order

**Day 1:** Notes 1-4 (architecture + auth)
**Day 2:** Notes 5-8 (trading domain)
**Day 3:** Notes 9-11 (observability)
**Day 4:** Notes 12-13 (infrastructure)
**Ongoing:** Notes 14-16 (background concepts, reference as needed)
