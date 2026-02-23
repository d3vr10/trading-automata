# Bot Monitoring & Lifecycle Guide

This guide explains the bot startup process, what to look for in the logs, and how to monitor bot health.

## Bot Startup Lifecycle

### Phase 1: Initialization (5-10 seconds)
```
🤖 Trading Bot Startup
====================
🗄️  Initializing database migrations...
⬇️  Checking strategy data cache...
✅ Cache found, using existing data
```

**What's happening:**
- Database migrations are running (schema setup)
- Strategy data cache is being checked for cached indicator values
- Configuration is being loaded from YAML files

**Common issues:**
- If migrations hang, check PostgreSQL connection
- If cache errors occur, the bot can continue with fresh calculations

### Phase 2: Mode Detection (< 1 second)
```
🔄 Multi-bot mode detected - using BotOrchestrator
```
Or:
```
🔄 Single-bot mode - using legacy TradingBot
```

**What's happening:**
- Bot auto-detects whether to run single-bot or multi-bot mode
- Single-bot: Uses legacy `TradingBot` class
- Multi-bot: Uses `BotOrchestrator` with multiple `BotInstance` objects

### Phase 3: Orchestrator Setup (5-15 seconds per bot)
```
Setting up 2/2 bot instance(s)...
Initializing bot 'alpha_bot' (alpaca paper)
```

**What's happening for each bot:**
1. Broker connection established
2. Data provider connected
3. Portfolio manager initialized
4. Strategies loaded from config
5. Health checks registered

**Expected messages:**
```
[alpha_bot] Setting up bot components...
[alpha_bot] Connected to data provider
[alpha_bot] Portfolio manager initialized (allocation: 5000.00 dollars, fence: hard)
[alpha_bot] Loading strategies from config/strategies.yaml...
[alpha_bot] Loaded 2 strategies: RSIATRTrendStrategy, SigmaSeriesFastStrategy
[alpha_bot] Monitoring symbols: BTC/USD, ETH/USD
[alpha_bot] ✅ Setup complete
```

### Phase 4: Trading Loop Start (< 1 second)
```
[alpha_bot] ✅ All startup checks passed, starting trading loop...
[alpha_bot] Trading loop started (poll interval: 60s)
```

**What's happening:**
- All startup checks passed
- Health check task spawned
- Trading loop begins monitoring for market bars
- Poll interval shows how often bot checks for new data

### Phase 5: Running
```
✅ Orchestrator setup complete: 2 bot(s) ready [alpha_bot, beta_bot]
  ▶️  Starting bot 'alpha_bot'
  ▶️  Starting bot 'beta_bot'
```

**What to expect:**
- Bot is now actively monitoring symbols
- Will log signals, orders, and trades as they occur
- May log "No position to sell for {symbol}" when checking for existing positions (normal)

## Understanding Log Levels

### INFO Level (default)
```
[alpha_bot] Connected to data provider
[alpha_bot] Loaded 2 strategies: RSIATRTrendStrategy
[alpha_bot] ✅ Setup complete
```
High-level status updates that indicate successful operations.

### DEBUG Level
```
[alpha_bot] Setting up bot components...
[alpha_bot] Registering built-in strategy classes...
[alpha_bot] Warming up strategies...
```
Detailed information about what the bot is doing. Enable with `LOG_LEVEL=DEBUG`.

### WARNING Level
```
WARNING: Broker disconnected, waiting for reconnection...
WARNING: Telegram bot not configured (no token)
```
Something unexpected but the bot can handle it.

### ERROR Level
```
ERROR: Failed to connect to data provider
ERROR: Setup failed, cannot start
```
Something went wrong. Bot may not be operational.

## Monitoring Health

### 1. Check Bot Status
```bash
# See if bot container is running
docker-compose ps

# Check latest logs
docker-compose logs --tail 20 trading-bot
```

### 2. Look for Trading Activity
```bash
# Filter for signals and trades
docker-compose logs trading-bot | grep -E "Signal|Order|Trade"

# Look for bars being processed
docker-compose logs trading-bot | grep "bar\|Bar"
```

### 3. Monitor Performance
```bash
# Watch CPU and memory usage
docker stats trading-bot

# Check database is responsive
docker-compose exec postgres psql -U postgres -d trading_bot -c "SELECT COUNT(*) FROM trades"
```

### 4. Verify Strategies
```bash
# Check which strategies are loaded
docker-compose logs trading-bot | grep "Loaded.*strategies"

# See monitored symbols
docker-compose logs trading-bot | grep "Monitoring symbols"
```

## Common Log Patterns

### Healthy Bot (All Startup Phases Completed)
```
[bot] ✅ Setup complete
[bot] ✅ All startup checks passed, starting trading loop...
[bot] Trading loop started (poll interval: 60s)
```
✅ Bot is ready to trade

### Bot Monitoring (Normal Operation)
```
[bot] Bar received: BTC/USD close=42500.00
[bot] Signal generated: BUY BTC/USD qty=0.1 confidence=0.85
[bot] Order submitted: order_id=xxx
```
✅ Bot is actively trading

### Broker Connection Issue
```
[bot] Broker disconnected, waiting for reconnection...
```
⚠️ Bot will retry connection automatically

### No Market Data
```
[bot] Bar received: None
```
⚠️ Market may be closed or data provider disconnected

### Position Management
```
No position to sell for QQQ
```
ℹ️ Normal - just means no open position exists for that symbol

## Troubleshooting by Symptom

### "Setup hangs at database migrations"
```bash
# Check database is healthy
docker-compose exec postgres pg_isready

# View migration logs
docker-compose logs postgres | tail -20

# Restart database
docker-compose restart postgres
```

### "Bot starts but no trading activity"
```bash
# Verify strategies loaded
docker-compose logs trading-bot | grep -i strategy

# Check if in production hours (market open?)
# Check if symbols have data
docker-compose logs trading-bot | grep "Bar received"

# See if signals are being generated
docker-compose logs trading-bot | grep -i signal
```

### "Strategies won't load"
```bash
# Check strategy config file exists
docker-compose exec trading-bot ls config/strategies.yaml

# Validate YAML syntax
docker-compose exec trading-bot python -c "import yaml; yaml.safe_load(open('config/strategies.yaml'))"

# Check strategy class names
docker-compose exec trading-bot python -c "from trading_bot.strategies.registry import StrategyRegistry; print(StrategyRegistry.REGISTRY)"
```

### "High memory usage"
```bash
# Check what's consuming memory
docker stats trading-bot

# Restart bot to reset memory
docker-compose restart trading-bot

# If problem persists, check database connections
docker-compose exec postgres psql -U postgres -d trading_bot -c "SELECT count(*) FROM pg_stat_activity"
```

## Performance Monitoring

### Log Frequency Analysis
```bash
# Count different log types per hour
docker-compose logs trading-bot --since 1h | grep -c "\[bot\]"

# Track signal frequency
docker-compose logs trading-bot | grep -c "Signal"

# Monitor errors
docker-compose logs trading-bot | grep -c "ERROR"
```

### Database Health
```bash
# Check table sizes
docker-compose exec postgres psql -U postgres -d trading_bot -c "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) FROM pg_tables ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC"

# Check index usage
docker-compose exec postgres psql -U postgres -d trading_bot -c "SELECT * FROM trades LIMIT 1"

# Monitor slow queries
docker-compose exec postgres psql -U postgres -d trading_bot -c "SELECT query, calls, mean_time FROM pg_stat_statements LIMIT 10"
```

## Log Rotation

To prevent log files from growing too large:

```bash
# Keep only last 100 lines
docker-compose logs --tail 100 trading-bot > bot_logs.txt

# Or use logrotate for persistent logging
# (if you mount logs to host filesystem)
```

## Advanced: Real-Time Monitoring

### Watch specific events
```bash
# Follow only signals
watch -n 1 'docker-compose logs --tail 50 trading-bot | grep -i signal'

# Follow only trades
watch -n 1 'docker-compose logs --tail 50 trading-bot | grep -i trade'

# Follow only errors
watch -n 1 'docker-compose logs --tail 50 trading-bot | grep -i error'
```

### Parse logs for metrics
```bash
# Count signals per symbol
docker-compose logs trading-bot | grep "Signal" | awk '{print $NF}' | sort | uniq -c

# Track P&L
docker-compose logs trading-bot | grep "Trade exit" | awk '{print $(NF-1)}'

# Monitor uptime
docker-compose logs trading-bot | grep "trading loop started"
```

## Related Documentation

- **Docker Setup:** [DOCKER_SETUP.md](DOCKER_SETUP.md)
- **Configuration:** [CONFIGURATION.md](CONFIGURATION.md)
- **Multi-Bot:** [../MULTI_BROKER_SETUP.md](../MULTI_BROKER_SETUP.md)
