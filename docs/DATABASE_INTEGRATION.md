# Database & Health Check Integration

## Overview

The TradingAutomata platform now has full database integration with PostgreSQL for persistent trade storage and health monitoring. This document explains how the system works and how to use it.

## Architecture

### Components

```
┌──────────────────┐
│  TradingBot      │
│  (main.py)       │
└────────┬─────────┘
         │
    ┌────▼────────────────────────┐
    │  Database Layer             │
    ├─────────────────────────────┤
    │  TradeRepository            │  (CRUD operations)
    │  - record_trade_entry()     │
    │  - record_trade_exit()      │
    │  - get_performance_metrics()│
    │  - etc.                     │
    └────┬────────────────────────┘
         │
    ┌────▼────────────────────────┐
    │  Health Checks              │
    ├─────────────────────────────┤
    │  HealthCheckRegistry        │  (monitors multiple brokers/strategies)
    │  - tracks connection status │
    │  - monitors data freshness  │
    │  - logs reconnect attempts  │
    └────┬────────────────────────┘
         │
    ┌────▼────────────────────────┐
    │  PostgreSQL Database        │
    ├─────────────────────────────┤
    │  trades                     │
    │  positions                  │
    │  performance_metrics        │
    │  trading_events             │
    │  health_checks              │
    └─────────────────────────────┘
```

## Database Integration in TradingBot

### Initialization (setup())

When the bot starts, it:

1. **Loads configuration** including `DATABASE_URL`
2. **Connects to PostgreSQL** asynchronously using psycopg3
3. **Creates TradeRepository** for database operations
4. **Creates HealthCheckRegistry** for health monitoring
5. **Registers health checks** for each strategy

### Trade Recording

When a signal is executed:

```python
# In _process_bar(), after order execution:
await self._record_trade_entry(strategy, signal, order_id)
```

This records:
- Trade symbol, strategy, broker
- Entry price, quantity, order ID
- Metadata (strategy name, signal action)

### Health Monitoring

The bot automatically:

1. **Tracks bar receives** - Updates `last_bar_timestamp` when data arrives
2. **Tracks order submission** - Updates `last_order_timestamp` when orders execute
3. **Records connection errors** - Increments error counter on exceptions
4. **Detects stale data** - Warns if no bars for >5 minutes
5. **Saves health status** - Persists to DB every 5 minutes
6. **Logs status** - Displays health dashboard every 10 minutes

### Cleanup

When the bot stops:

1. **Saves final health checks** to database
2. **Closes database connection** gracefully
3. **Cancels monitoring tasks**
4. **Logs final statistics**

## Configuration

### Environment Variables

```env
# Database connection
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/trading-automata

# Connection pool size
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
```

### config/config.yml

```yaml
app:
  database_url: postgresql://postgres:postgres@localhost:5432/trading-automata
  database_pool_size: 10
  database_max_overflow: 20
```

Precedence (highest to lowest):
1. Environment variables
2. .env file
3. config.yml
4. Defaults

## Health Check Manager

### HealthCheckManager

Tracks health for a single broker/strategy combination:

```python
# Create a health check
health_check = HealthCheckManager(conn, broker='alpaca', strategy='rsi_atr_trend')

# Record activity
await health_check.record_bar_received()
await health_check.record_order_submitted()
await health_check.record_connection_error("Connection timeout")

# Check status
if health_check.is_stale():
    logger.warning("Data is stale")

if not health_check.is_healthy:
    logger.error("Bot is unhealthy")

# Get reconnection info
if health_check.should_attempt_reconnect():
    delay = health_check.get_reconnect_delay()
    # Attempt reconnection after delay
    await health_check.record_reconnect_attempt(success=True)
```

### HealthCheckRegistry

Manages multiple health checks:

```python
# Register checks (done automatically in setup())
registry = HealthCheckRegistry(conn)
alpaca_check = registry.register('alpaca', 'rsi_atr_trend')
coinbase_check = registry.register('coinbase', 'momentum')

# Save all checks periodically
await registry.save_all()

# Get status
status = await registry.get_all_status()
unhealthy = registry.get_unhealthy_checks()
stale = registry.get_stale_checks()

# Log dashboard
registry.log_all_status()
```

## Database Operations

### Querying Trade Data

```bash
# Connect to database
psql postgresql://postgres:postgres@localhost:5432/trading-automata

# View recent trades
SELECT symbol, entry_price, exit_price, pnl_percent, strategy
FROM trades
ORDER BY entry_timestamp DESC
LIMIT 10;

# View open positions
SELECT symbol, quantity, entry_price, current_price, strategy
FROM positions
WHERE is_open = true;

# View health checks
SELECT broker, strategy, is_healthy, connection_errors, checked_at
FROM health_checks
ORDER BY checked_at DESC
LIMIT 10;
```

### Using TradeRepository

```python
# Record trade entry
trade_id = await repo.record_trade_entry(
    symbol="BTC/USD",
    strategy="rsi_atr_trend",
    broker="alpaca",
    entry_price=Decimal("50000"),
    entry_quantity=Decimal("0.1"),
    entry_order_id="order_123"
)

# Record trade exit
await repo.record_trade_exit(
    trade_id=trade_id,
    exit_price=Decimal("51000"),
    exit_quantity=Decimal("0.1"),
    exit_order_id="order_124"
)

# Get performance metrics
metrics = await repo.get_performance_metrics(
    strategy="rsi_atr_trend",
    days=7
)
# Returns: {
#   'total_trades': 42,
#   'winning_trades': 24,
#   'win_rate': 57.14,
#   'profit_factor': 1.83,
#   'sharpe_ratio': 1.25
# }

# Get open positions
positions = await repo.get_open_positions(strategy="rsi_atr_trend")
```

## Monitoring Dashboard

The bot logs health status every 10 minutes:

```
=== Health Check Status ===
alpaca:rsi_atr_trend: 🟢 HEALTHY | errors: 0 | reconnects: 0/5
alpaca:momentum: 🟢 HEALTHY | errors: 1 | reconnects: 0/5
coinbase:buy_and_hold: 🔴 UNHEALTHY | errors: 5 | reconnects: 2/5

⚠️  1 unhealthy checks detected
⚠️  0 checks with stale data
```

## Database Maintenance

### Check Database Size

```bash
psql -U postgres -d trading-automata -c "SELECT pg_size_pretty(pg_database_size('trading-automata'));"
```

### Backup Database

```bash
pg_dump -U postgres trading-automata > backup_$(date +%Y%m%d).sql
```

### Restore Database

```bash
psql -U postgres trading-automata < backup_20260215.sql
```

### Archive Old Trades

```sql
-- Move trades older than 6 months to archive table
CREATE TABLE trades_archive AS
SELECT * FROM trades
WHERE entry_timestamp < NOW() - INTERVAL '6 months';

DELETE FROM trades
WHERE entry_timestamp < NOW() - INTERVAL '6 months';
```

## Troubleshooting

### Issue: "Failed to connect to database"

```
Logger: Error: Failed to connect to database: connection refused

Check:
1. PostgreSQL is running: psql -U postgres
2. Database exists: psql -l | grep trading-automata
3. DATABASE_URL is correct: echo $DATABASE_URL
4. Credentials are valid
```

### Issue: "Connection pool exhausted"

```
Logger: Warning: Connection pool exhausted

Fix:
1. Increase pool size in .env:
   DATABASE_POOL_SIZE=20
   DATABASE_MAX_OVERFLOW=40

2. Check for connection leaks in logs
3. Restart bot to reset connections
```

### Issue: "Health check timeout - bot marked unhealthy"

```
Logger: Error: Bot marked unhealthy after 3 errors

Possible causes:
1. Network connectivity issue
2. Broker API downtime
3. WebSocket disconnection
4. Rate limit exceeded

Solution:
1. Check broker status
2. Check network connectivity: ping api.alpaca.markets
3. Check error logs for details
4. Restart bot to trigger reconnection logic
```

### Issue: "Data is stale" warning

```
Logger: Warning: Data is stale: 301s since last bar

Possible causes:
1. Market is closed (outside trading hours)
2. WebSocket disconnected
3. No new bars available for symbol

Solution:
1. Check if market is open
2. Verify symbol is trading
3. Check broker WebSocket connection
4. Restart data provider
```

## Performance Tips

1. **Connection Pooling**: Bot automatically pools connections (min: 10, max: 30)
2. **Async Operations**: All DB operations are async and non-blocking
3. **Batch Inserts**: Health checks are batched and saved every 5 minutes
4. **Indexes**: Tables are indexed on common query fields (symbol, strategy, timestamp)
5. **Pagination**: Use LIMIT clause for large result sets
6. **Archiving**: Archive old trades (>6 months) to separate table for faster queries

## Next Steps

### Week 2: Alerts & Notifications

Once database is stable, implement:
- Trade completion alerts (Telegram, email)
- Loss alerts (portfolio drops >X%)
- Health alerts (unhealthy checks)
- Daily performance reports

### Future: API Layer

Build REST API on top of database:

```python
from fastapi import FastAPI
from trading_automata.database import TradeRepository

app = FastAPI()

@app.get("/api/trades")
async def get_trades(symbol: str, days: int = 7):
    trades = await repo.get_trades_by_symbol(symbol, days)
    return trades

@app.get("/api/metrics/{strategy}")
async def get_metrics(strategy: str, days: int = 7):
    metrics = await repo.get_performance_metrics(strategy, days)
    return metrics
```

## Files Modified

- ✅ `src/main.py` - Database and health check integration
- ✅ `src/database/health.py` - Health check manager (NEW)
- ✅ `src/database/__init__.py` - Export health check classes
- ✅ `config/settings.py` - Database configuration fields
- ✅ `docs/DATABASE_SETUP.md` - Database setup guide

## Schema Reference

### health_checks Table

```sql
CREATE TABLE health_checks (
    id BIGSERIAL PRIMARY KEY,
    broker VARCHAR(50) NOT NULL,
    strategy VARCHAR(100) NOT NULL,
    is_healthy BOOLEAN DEFAULT true,
    last_bar_timestamp TIMESTAMP,
    last_order_timestamp TIMESTAMP,
    connection_errors INTEGER DEFAULT 0,
    checked_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_broker_strategy ON health_checks(broker, strategy);
CREATE INDEX idx_checked_at ON health_checks(checked_at);
```

See [DATABASE_SETUP.md](DATABASE_SETUP.md) for complete schema.

---

## Summary

The bot now:
- ✅ **Records all trades** to PostgreSQL database
- ✅ **Monitors health** of all connections and data streams
- ✅ **Tracks performance** with metrics and analytics
- ✅ **Persists state** for historical analysis
- ✅ **Provides API-ready** data for future web interface

Ready to go live! 🚀
