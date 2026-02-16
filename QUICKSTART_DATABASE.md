# Quick Start: Database & Health Checks

Get the trading bot with database integration running in 5 minutes.

## Step 1: Start PostgreSQL (2 minutes)

### Option A: Docker (Recommended)

```bash
# Start PostgreSQL container
docker run -d \
  --name trading-bot-db \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=trading_bot \
  -p 5432:5432 \
  postgres:15

# Verify it's running
docker ps | grep trading-bot-db
# Should show: ... postgres:15 ... Up X seconds
```

### Option B: macOS (Homebrew)

```bash
brew install postgresql@15
brew services start postgresql@15

# Create database
createdb -U postgres trading_bot
```

### Option C: Linux (apt)

```bash
sudo apt-get install postgresql-15
sudo systemctl start postgresql

# Create database
sudo -u postgres createdb trading_bot
```

## Step 2: Initialize Database Schema (1 minute)

```bash
# Navigate to project root
cd /home/d3vr10/Documents/Projects/trading-bot

# Initialize database schema
python -m src.database.init

# Expected output:
# ✅ Connected to PostgreSQL
# ✅ Database schema created successfully
# ✅ Created tables: ['trades', 'positions', 'performance_metrics', 'trading_events', 'health_checks']
# ✅ Database initialization complete!
```

## Step 3: Configure .env (1 minute)

```bash
# Copy template
cp .env.example .env

# Edit .env and verify:
cat .env | grep DATABASE
# Should show:
# DATABASE_URL=postgresql://postgres:postgres@localhost:5432/trading_bot
# DATABASE_POOL_SIZE=10
# DATABASE_MAX_OVERFLOW=20
```

## Step 4: Run the Bot (1 minute)

```bash
# Alpaca paper trading (recommended for testing)
BROKER=alpaca TRADING_ENV=paper python -m src.main

# Expected output:
# INFO | Loading configuration...
# INFO | Trading Bot initialized - Environment: paper
# INFO | Creating alpaca broker...
# INFO | Connected to broker. Account: ..., Portfolio Value: $...
# INFO | Connecting to database...
# INFO | ✅ Connected to PostgreSQL database
# INFO | Registering strategies...
# INFO | Loaded 4 active strategies
# INFO | Registered 4 health checks
# INFO | Starting trading loop...
# INFO | Monitoring symbols: ['SPY', 'AAPL', ...]
```

## Step 5: Monitor in Another Terminal

```bash
# Open another terminal and check database

# Connect to database
psql postgresql://postgres:postgres@localhost:5432/trading_bot

# View recent trades
SELECT symbol, strategy, entry_price, pnl_percent
FROM trades
ORDER BY entry_timestamp DESC
LIMIT 5;

# View health status
SELECT broker, strategy, is_healthy, connection_errors, checked_at
FROM health_checks
ORDER BY checked_at DESC
LIMIT 5;

# Exit psql
\q
```

## What Should Happen

### Logs (From Bot)

Every minute:
```
INFO | Monitoring symbols: ['SPY', 'AAPL', ...]
```

Every 5 minutes:
```
DEBUG | Health check saved - is_healthy: True, errors: 0
```

Every 10 minutes:
```
INFO | === Health Check Status ===
INFO | alpaca:buy_and_hold: 🟢 HEALTHY | errors: 0 | reconnects: 0/5
INFO | alpaca:mean_reversion: 🟢 HEALTHY | errors: 0 | reconnects: 0/5
INFO | alpaca:momentum: 🟢 HEALTHY | errors: 0 | reconnects: 0/5
INFO | alpaca:rsi_atr_trend: 🟢 HEALTHY | errors: 0 | reconnects: 0/5
```

When trades execute:
```
INFO | Strategy mean_reversion generated signal: Signal(symbol='SPY', action='buy', ...)
INFO | Signal executed as order order_xyz
INFO | Recorded trade entry #1 for SPY
```

### Database (From psql)

```sql
trading_bot=# SELECT COUNT(*) FROM trades;
 count
-------
     5
(1 row)

trading_bot=# SELECT COUNT(*) FROM health_checks;
 count
-------
     4
(1 row)

trading_bot=# SELECT * FROM trades ORDER BY entry_timestamp DESC LIMIT 1;
 id | symbol | strategy      | broker  | entry_price | entry_quantity | gross_pnl | pnl_percent | is_winning_trade | entry_timestamp
----+--------+---------------+---------+-------------+----------------+-----------+-------------+------------------+---
  1 | SPY    | mean_reversion| alpaca  | 450.25      | 1.0            | NULL      | NULL        | NULL             | 2026-02-15 14:30:00
```

## Troubleshooting

### Issue: "Connection refused"

```bash
# Check PostgreSQL is running
docker ps | grep postgres
# or
brew services list | grep postgres
# or
sudo systemctl status postgresql

# If not running, start it
docker start trading-bot-db
# or
brew services start postgresql
```

### Issue: "database trading_bot does not exist"

```bash
# Check database exists
psql -U postgres -l | grep trading_bot

# If not, create it
psql -U postgres -c "CREATE DATABASE trading_bot;"

# Then initialize schema
python -m src.database.init
```

### Issue: "Failed to connect to database" in bot

```bash
# Test database URL
psql postgresql://postgres:postgres@localhost:5432/trading_bot

# If that works, check .env file
cat .env | grep DATABASE_URL

# If URL is wrong, update it and restart bot
```

### Issue: "No symbols in logs"

```bash
# Check strategies.yaml exists
ls config/strategies.yaml

# Check it has symbols configured
cat config/strategies.yaml | grep symbols

# Example should show:
# symbols:
#   - SPY
#   - AAPL
#   - GOOGL
#   - MSFT
```

## Next Steps

### 1. Run for 24 Hours
Let the bot run in paper trading for at least 24 hours to verify:
- ✅ Database persists data
- ✅ Health checks run every 5 minutes
- ✅ No crashes or errors
- ✅ Trades recorded correctly

### 2. Check Performance

```sql
-- View performance metrics
SELECT strategy, total_trades, win_rate, profit_factor
FROM performance_metrics
ORDER BY metric_date DESC
LIMIT 5;

-- View open positions
SELECT * FROM positions WHERE is_open = true;

-- View P&L by symbol
SELECT symbol, COUNT(*) as trades, SUM(gross_pnl) as total_pnl
FROM trades
GROUP BY symbol
ORDER BY total_pnl DESC;
```

### 3. Switch to Live (When Ready)

```bash
# Update .env
BROKER=alpaca
TRADING_ENV=live

# Get live API keys from https://app.alpaca.markets/

# Run bot
python -m src.main
```

### 4. Add Alerts (Week 2)

After confirming database works, add:
- Telegram notifications on trades
- Email alerts on losses
- Daily performance reports

## Files to Know

**Database:**
- `src/database/init.py` - Schema creation
- `src/database/repository.py` - Trade CRUD operations
- `src/database/health.py` - Health monitoring
- `docs/DATABASE_SETUP.md` - Full reference

**Configuration:**
- `.env` - Environment variables
- `config/settings.py` - Settings class
- `config/strategies.yaml` - Strategy config

**Main Bot:**
- `src/main.py` - Bot orchestration
- `src/brokers/` - Broker implementations
- `src/strategies/` - Strategy implementations

## Connection Info

```
Host: localhost
Port: 5432
Database: trading_bot
User: postgres
Password: postgres
```

## Common Commands

```bash
# View bot logs (in real-time)
tail -f /tmp/trading_bot.log  # if configured

# Check database size
psql -c "SELECT pg_size_pretty(pg_database_size('trading_bot'));"

# Backup database
pg_dump -U postgres trading_bot > backup.sql

# Restore database
psql -U postgres trading_bot < backup.sql

# Clear all trades (careful!)
psql -U postgres -d trading_bot -c "DELETE FROM trades; DELETE FROM health_checks;"
```

## Expected Resource Usage

**Database:**
- Initial size: ~5 MB
- Per 1000 trades: ~1 MB
- Per 1 month: ~50-100 MB

**Bot Memory:**
- Initial: ~150 MB
- Per strategy: ~20 MB
- Stable: 200-300 MB

**Network:**
- Database writes: ~1 KB per minute
- Health checks: ~100 bytes per 5 minutes
- Minimal network usage

## Success Criteria

Bot is working when:

✅ Starts without errors
✅ Shows "✅ Connected to PostgreSQL"
✅ Logs "Registered N health checks"
✅ Saves health checks every 5 minutes
✅ Logs health dashboard every 10 minutes
✅ Trades appear in database
✅ No database errors in logs
✅ Runs for 24+ hours without crashes

## Getting Help

See detailed docs:
- **DATABASE_SETUP.md** - Full database reference
- **DATABASE_INTEGRATION.md** - Integration guide
- **WEEK1_COMPLETION_SUMMARY.md** - Complete feature summary

---

**You're all set!** 🚀

Start the bot and watch the database fill with trading data.
