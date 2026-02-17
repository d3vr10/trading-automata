# PostgreSQL Database Setup

Trading bot uses PostgreSQL for persistent storage of trades, positions, and performance metrics. Designed to be API-ready with raw SQL (no ORM overhead).

## Quick Start

### 1. Install PostgreSQL

**macOS:**
```bash
brew install postgresql
brew services start postgresql
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql
```

**Docker (recommended):**
```bash
docker run -d \
  --name trading-bot-db \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=trading_bot \
  -p 5432:5432 \
  postgres:15
```

### 2. Create Database

```bash
createdb -U postgres trading_bot
# or via Docker
docker exec trading-bot-db createdb -U postgres trading_bot
```

### 3. Initialize Schema

```bash
# From project root
python -m trading_bot.database.init
```

Expected output:
```
✅ Connected to PostgreSQL
✅ Database schema created successfully
✅ Created tables: ['trades', 'positions', 'performance_metrics', 'trading_events', 'health_checks']
✅ Database initialization complete!
```

### 4. Configure Connection

**Option A: Environment Variable**
```bash
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/trading_bot"
python -m trading_bot.main
```

**Option B: .env File**
```env
# .env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/trading_bot
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
```

**Option C: Docker**
```bash
docker run -e DATABASE_URL="postgresql://user:pass@host:5432/trading_bot" my-bot
```

---

## Database Schema

### Tables

#### `trades` - Trading entry/exit records
```
Stores every trade: entry price, exit price, P&L, performance metrics
Indexed on: (symbol, timestamp), (strategy, timestamp), winning trades
```

**Columns:**
- `id` - Unique trade ID
- `symbol` - Trading symbol (BTC/USD, EUR/USD, etc.)
- `strategy` - Strategy that generated the trade
- `broker` - Broker used (alpaca, coinbase)
- `entry_timestamp` - When position opened
- `entry_price` - Price at entry
- `entry_quantity` - Quantity entered
- `exit_timestamp` - When position closed
- `exit_price` - Price at exit
- `exit_quantity` - Quantity exited
- `gross_pnl` - Profit/loss in currency
- `pnl_percent` - Return percentage
- `is_winning_trade` - Boolean (true/false)
- `hold_duration_seconds` - How long position was held

#### `positions` - Current open positions
```
Tracks all open positions for risk management
Indexed on: symbol, is_open, strategy
```

**Columns:**
- `id` - Position ID
- `symbol` - Trading symbol
- `strategy` - Opening strategy
- `quantity` - Position size
- `entry_price` - Entry price
- `current_price` - Last market price
- `is_open` - Boolean (true = open, false = closed)
- `stop_loss` - Stop loss price
- `take_profit` - Take profit price
- `opened_at` - Timestamp opened
- `closed_at` - Timestamp closed

#### `performance_metrics` - Daily/hourly statistics
```
Snapshots of strategy performance
Indexed on: metric_date, strategy
```

**Columns:**
- `metric_date` - Time of metric
- `period` - 'hourly', 'daily', 'weekly'
- `strategy` - Strategy name
- `total_trades` - Count of trades
- `winning_trades` - Winning trade count
- `win_rate` - Win rate percentage
- `gross_profit` - Total profit
- `gross_loss` - Total loss
- `profit_factor` - Profit / Loss ratio
- `sharpe_ratio` - Risk-adjusted return

#### `trading_events` - Bot events log
```
Logs significant events (errors, reconnects, etc.)
Indexed on: event_type, severity, timestamp
```

**Columns:**
- `event_type` - 'trade', 'error', 'connection', etc.
- `severity` - 'info', 'warning', 'error', 'critical'
- `message` - Event description
- `strategy` - Related strategy
- `symbol` - Related symbol
- `resolved` - Has event been addressed?

#### `health_checks` - Bot health monitoring
```
Tracks bot connectivity and performance
Indexed on: broker, checked_at
```

**Columns:**
- `broker` - Broker name
- `strategy` - Strategy monitored
- `is_healthy` - Boolean health status
- `last_bar_timestamp` - When last bar received
- `last_order_timestamp` - When last order placed
- `connection_errors` - Error count

---

## API Usage (Trade Repository)

The `TradeRepository` class provides methods for database operations:

```python
from trading_bot.database import TradeRepository
import psycopg

# Connect
conn = await psycopg.AsyncConnection.connect(database_url)
repo = TradeRepository(conn)

# Record trade entry
trade_id = await repo.record_trade_entry(
    symbol="BTC/USD",
    strategy="rsi_atr_trend",
    broker="coinbase",
    entry_price=Decimal("42500"),
    entry_quantity=Decimal("0.5"),
    entry_order_id="abc123"
)

# Record trade exit
await repo.record_trade_exit(
    trade_id=trade_id,
    exit_price=Decimal("43000"),
    exit_quantity=Decimal("0.5"),
    exit_order_id="def456"
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
#   ...
# }

# Get open positions
positions = await repo.get_open_positions(strategy="rsi_atr_trend")

# Get recent trades
trades = await repo.get_trades_by_symbol(symbol="BTC/USD", days=7)
```

---

## Querying the Database

### Using psycopg directly:

```python
import psycopg

conn = await psycopg.AsyncConnection.connect(database_url)

# Get win rate for today
result = await conn.execute("""
    SELECT
        COUNT(*) as total,
        COUNT(CASE WHEN is_winning_trade = true THEN 1 END) as wins,
        ROUND(COUNT(CASE WHEN is_winning_trade = true THEN 1 END)::NUMERIC / COUNT(*) * 100, 2) as win_rate
    FROM trades
    WHERE entry_timestamp > NOW() - INTERVAL '1 day'
""")

for row in result:
    print(f"Trades: {row['total']}, Win Rate: {row['win_rate']}%")
```

### Using CLI tools:

```bash
# Connect via psql
psql postgresql://postgres:postgres@localhost:5432/trading_bot

# List recent trades
SELECT symbol, entry_price, exit_price, pnl_percent, is_winning_trade
FROM trades
ORDER BY entry_timestamp DESC
LIMIT 10;

# Win rate this week
SELECT
    COUNT(*) as total_trades,
    SUM(CASE WHEN is_winning_trade = true THEN 1 ELSE 0 END) as winning_trades,
    ROUND(SUM(CASE WHEN is_winning_trade = true THEN 1 ELSE 0 END)::NUMERIC / COUNT(*) * 100, 2) as win_rate
FROM trades
WHERE entry_timestamp > NOW() - INTERVAL '7 days';

# Most profitable symbols
SELECT symbol, SUM(gross_pnl) as total_pnl, COUNT(*) as trades
FROM trades
WHERE exit_timestamp IS NOT NULL
GROUP BY symbol
ORDER BY total_pnl DESC;
```

---

## Future API Integration

The database is designed to be API-ready. When you're ready to build an API:

```python
# This will work perfectly with FastAPI, Flask, Django, etc.

# Example FastAPI endpoint
from fastapi import FastAPI
from trading_bot.database import TradeRepository

app = FastAPI()

@app.get("/api/trades")
async def get_trades(symbol: str, days: int = 7):
    repo = TradeRepository(conn)
    trades = await repo.get_trades_by_symbol(symbol, days)
    return trades

@app.get("/api/metrics/{strategy}")
async def get_metrics(strategy: str, days: int = 7):
    repo = TradeRepository(conn)
    metrics = await repo.get_performance_metrics(strategy, days)
    return metrics
```

---

## Monitoring & Maintenance

### Check Database Size
```bash
psql -c "SELECT pg_size_pretty(pg_database_size('trading_bot'));"
```

### Backup Database
```bash
pg_dump -U postgres trading_bot > backup.sql
```

### Restore Database
```bash
psql -U postgres trading_bot < backup.sql
```

### View Recent Trades
```bash
psql -c "SELECT symbol, pnl_percent, is_winning_trade FROM trades ORDER BY entry_timestamp DESC LIMIT 20;"
```

### Performance Statistics
```bash
psql -c "
SELECT
    strategy,
    COUNT(*) as total,
    COUNT(CASE WHEN is_winning_trade = true THEN 1 END) as wins,
    ROUND(AVG(pnl_percent), 2) as avg_return,
    MAX(pnl_percent) as best_trade,
    MIN(pnl_percent) as worst_trade
FROM trades
WHERE exit_timestamp IS NOT NULL
GROUP BY strategy;
"
```

---

## Troubleshooting

### Connection Error: "Connection refused"
```bash
# Check if PostgreSQL is running
psql -U postgres -d postgres

# If not running, start it
brew services start postgresql  # macOS
sudo systemctl start postgresql # Linux
docker start trading-bot-db      # Docker
```

### "database trading_bot does not exist"
```bash
createdb -U postgres trading_bot
python -m trading_bot.database.init
```

### Connection Pool Exhausted
```env
# Increase pool size in .env
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30
```

### Slow Queries
```bash
# Enable query logging in PostgreSQL
psql -U postgres -d trading_bot
ALTER DATABASE trading_bot SET log_min_duration_statement = 1000;

# View slow queries
SELECT query, calls, mean_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC;
```

---

## Performance Tips

1. **Indexes**: Queries are indexed on common fields (symbol, strategy, timestamp)
2. **Async**: All operations use async/await - doesn't block trading loop
3. **Connection Pool**: Reuses connections, don't create new ones per query
4. **Pagination**: Use LIMIT clause for large result sets
5. **Archiving**: Consider archiving old trades (>6 months) to separate table

---

## Configuration Reference

```env
# Database URL (required)
DATABASE_URL=postgresql://user:password@host:5432/trading_bot

# Connection pool size (default: 10)
DATABASE_POOL_SIZE=10

# Maximum overflow connections (default: 20)
DATABASE_MAX_OVERFLOW=20
```

---

## Next: Building an API

When you're ready to expose trading data via API:
1. Create FastAPI app
2. Use `TradeRepository` for queries
3. Return Pydantic models
4. Deploy as microservice (if desired)

The database foundation is already in place! 🎯
