# Coinbase Deployment Guide - Multi-Bot Trading System

This guide walks you through deploying the multi-bot orchestration system to trade on Coinbase (paper or live).

## Prerequisites

### 1. Coinbase Advanced Trading Account Setup

#### For Paper Trading:
- Create Coinbase account at https://www.coinbase.com
- Enable API access in Settings → API → Create API Key
- Select "Trading" permission scope
- **IMPORTANT:** Copy `API Key`, `Secret Key`, and `Passphrase` immediately (passphrase shown once only!)
- Save these securely

#### For Live Trading:
- Same as paper, but ensure account has actual funds deposited
- Start with small allocation amounts (e.g., $100-$500) for first test
- Follow testing checklist completely before scaling

### 2. Environment Variables

Create or update your `.env` file in the project root:

```bash
# Coinbase API Credentials
COINBASE_API_KEY="your_api_key_here"
COINBASE_SECRET_KEY="your_secret_key_here"
COINBASE_PASSPHRASE="your_passphrase_here"

# Database (PostgreSQL)
DATABASE_URL="postgresql://user:password@localhost:5432/trading_bot_db"

# Telegram (optional, but recommended for notifications)
TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
TELEGRAM_CHAT_ID="your_chat_id"

# Multi-bot mode
BOT_MODE="multi"
```

### 3. Database Setup

Run the migration to add `bot_name` columns:

```bash
# Ensure your database is running
# Then run:
alembic upgrade 003
```

This adds:
- `bot_name` column to: trades, positions, trading_events, health_checks, bot_sessions
- Indexes for efficient filtering
- Zero-downtime migration (existing rows get NULL/"legacy")

### 4. Python Environment

```bash
# Install dependencies
pip install -r requirements.txt

# Verify installation
python -c "from trading_bot.orchestration.orchestrator import BotOrchestrator; print('✓ Multi-bot system ready')"
```

---

## Configuration

### Single Coinbase Bot (Simplest Setup)

Create `config/bots.yaml`:

```yaml
global:
  database_url: "${DATABASE_URL}"
  telegram_token: "${TELEGRAM_BOT_TOKEN}"
  telegram_chat_id: "${TELEGRAM_CHAT_ID}"
  log_level: "INFO"

bots:
  - name: "coinbase_bot"
    enabled: true
    broker:
      type: "coinbase"
      api_key: "${COINBASE_API_KEY}"
      secret_key: "${COINBASE_SECRET_KEY}"
      passphrase: "${COINBASE_PASSPHRASE}"
    allocation:
      type: "dollars"
      amount: 100.00                    # Start with $100 for testing
    fence:
      type: "hard"                      # Prevents over-allocation
      overage_pct: 0.0
    risk:
      stop_loss_pct: 2.0
      take_profit_pct: 6.0
      max_position_size: 50.00          # Max $50 per trade
      max_portfolio_risk: 5.0
    trade_frequency:
      poll_interval_minutes: 1          # Check for signals every 1 minute
    strategy_config: "config/strategies.yaml"
    data_provider:
      type: "alpaca"
      api_key: "${ALPACA_API_KEY}"      # Data provider (separate from broker)
      secret_key: "${ALPACA_SECRET_KEY}"
```

### Multiple Bots with Different Strategies

Create `config/bots.yaml`:

```yaml
global:
  database_url: "${DATABASE_URL}"
  telegram_token: "${TELEGRAM_BOT_TOKEN}"
  telegram_chat_id: "${TELEGRAM_CHAT_ID}"
  log_level: "INFO"

bots:
  # Fast momentum bot - aggressive, small capital
  - name: "fast_momentum"
    enabled: true
    broker:
      type: "coinbase"
      api_key: "${COINBASE_API_KEY}"
      secret_key: "${COINBASE_SECRET_KEY}"
      passphrase: "${COINBASE_PASSPHRASE}"
    allocation:
      type: "dollars"
      amount: 150.00                    # $150 for fast signals
    fence:
      type: "hard"
    risk:
      stop_loss_pct: 1.5
      take_profit_pct: 3.0
      max_position_size: 75.00
      max_portfolio_risk: 3.0
    trade_frequency:
      poll_interval_minutes: 1
    strategy_config: "config/strategies.yaml"

  # Conservative alpha bot - steady, medium capital
  - name: "conservative_alpha"
    enabled: true
    broker:
      type: "coinbase"
      api_key: "${COINBASE_API_KEY}"
      secret_key: "${COINBASE_SECRET_KEY}"
      passphrase: "${COINBASE_PASSPHRASE}"
    allocation:
      type: "dollars"
      amount: 250.00                    # $250 for mean-reversion
    fence:
      type: "hard"
    risk:
      stop_loss_pct: 2.0
      take_profit_pct: 6.0
      max_position_size: 100.00
      max_portfolio_risk: 5.0
    trade_frequency:
      poll_interval_minutes: 5          # Slower signals
    strategy_config: "config/strategies.yaml"

  # Bull market tracker - long-only, larger capital
  - name: "bull_tracker"
    enabled: false                      # Disabled until bull market confirmed
    broker:
      type: "coinbase"
      api_key: "${COINBASE_API_KEY}"
      secret_key: "${COINBASE_SECRET_KEY}"
      passphrase: "${COINBASE_PASSPHRASE}"
    allocation:
      type: "dollars"
      amount: 300.00
    fence:
      type: "hard"
    risk:
      stop_loss_pct: 1.0
      take_profit_pct: 4.0
      max_position_size: 150.00
      max_portfolio_risk: 5.0
    trade_frequency:
      poll_interval_minutes: 5
    strategy_config: "config/strategies.yaml"
```

### Strategy Configuration

Update `config/strategies.yaml` to include Sigma Series strategies:

```yaml
strategies:
  SigmaSeriesFastStrategy:
    enabled: true
    symbols:
      - "BTC-USD"
      - "ETH-USD"
    filters:
      min_volume: 100000
      min_atr: 50
      max_atr: 2000
      volatility_lookback: 20

  SigmaSeriesAlphaStrategy:
    enabled: true
    symbols:
      - "BTC-USD"
      - "ETH-USD"
      - "SOL-USD"
    filters:
      min_volume: 100000
      min_atr: 50
      max_atr: 2000

  SigmaSeriesAlphaBullStrategy:
    enabled: false                    # Enable in confirmed bull markets
    symbols:
      - "BTC-USD"
      - "ETH-USD"
    filters:
      min_volume: 100000
      min_atr: 50
      max_atr: 2000
```

---

## Deployment Options

### Option A: Local Python (Development/Testing)

```bash
# Navigate to project directory
cd /home/d3vr10/Documents/Projects/trading-bot

# Ensure environment variables are loaded
export $(cat .env | xargs)

# Start the system
python -m trading_bot.main

# Output should show:
# Multi-bot mode detected - using BotOrchestrator
# [coinbase_bot] Connecting to Coinbase broker...
# [coinbase_bot] Initializing strategies...
# [coinbase_bot] Starting trading loop...
```

### Option B: Docker Compose (Production)

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: trading_bot_db
      POSTGRES_USER: trading_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  trading-bot:
    build: .
    environment:
      DATABASE_URL: "postgresql://trading_user:${DB_PASSWORD}@postgres:5432/trading_bot_db"
      COINBASE_API_KEY: ${COINBASE_API_KEY}
      COINBASE_SECRET_KEY: ${COINBASE_SECRET_KEY}
      COINBASE_PASSPHRASE: ${COINBASE_PASSPHRASE}
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      TELEGRAM_CHAT_ID: ${TELEGRAM_CHAT_ID}
      BOT_MODE: "multi"
    depends_on:
      - postgres
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs
    restart: unless-stopped

volumes:
  postgres_data:
```

Run with:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

---

## Verification Steps

### 1. Broker Connection
```bash
# Check logs for successful connection
docker-compose logs trading-bot | grep "Connected to Coinbase"

# Or in local terminal:
# Should see: [coinbase_bot] Connected to Coinbase broker successfully
```

### 2. Strategy Registration
```bash
# Verify Sigma strategies loaded
docker-compose logs trading-bot | grep "SigmaSeriesFastStrategy\|SigmaSeriesAlphaStrategy\|SigmaSeriesAlphaBullStrategy"
```

### 3. Data Flow
```bash
# Check that bars are being received
docker-compose logs trading-bot | grep "bars received"

# Example: [2026-02-22 10:30:45] coinbase_bot - 50 bars received for BTC-USD
```

### 4. Signal Generation
```bash
# Monitor signal creation
docker-compose logs trading-bot | grep "Signal generated"

# Example: [2026-02-22 10:35:20] coinbase_bot - Signal: BUY BTC-USD @ $42,500
```

### 5. Telegram Notification (if enabled)
```bash
# Should receive message with format:
# [coinbase_bot] Connected to Coinbase broker
# [coinbase_bot] Health check: BTC-USD | SigmaSeriesFastStrategy - HEALTHY
```

### 6. Database Records
```bash
# Query trades created
psql -U trading_user -d trading_bot_db << EOF
SELECT bot_name, symbol, action, quantity, price, created_at
FROM trades
WHERE bot_name = 'coinbase_bot'
ORDER BY created_at DESC
LIMIT 10;
EOF
```

---

## Monitoring Commands

Once running, use Telegram commands to monitor:

```
/bots                      # List all bot status + virtual balance
/status coinbase_bot       # Detailed status for specific bot
/trades coinbase_bot open  # Show open positions
/metrics coinbase_bot      # P&L chart + statistics
/pause_bot coinbase_bot    # Pause trading (keeps collecting data)
/resume_bot coinbase_bot   # Resume trading
```

---

## Troubleshooting

### Issue: "Multi-bot mode not detected"
**Cause:** `config/bots.yaml` not found
**Fix:** Ensure file exists in correct location with proper YAML syntax

### Issue: "Cannot connect to Coinbase"
**Cause:** Invalid API credentials or network issue
**Fix:**
- Verify API key, secret, and passphrase in `.env`
- Test Coinbase API directly: `curl -H "CB-ACCESS-KEY: {key}" https://api.coinbase.com/api/v3/accounts`

### Issue: "Hard fence rejected order"
**Cause:** Order cost exceeds `allocation.amount`
**Expected:** This is correct behavior. Either increase allocation or reduce position size
**Verify:** Check logs for "Hard fence rejected" message

### Issue: "No signals being generated"
**Cause:** Indicators not converging, filters too strict, or market conditions misaligned with strategy
**Debug:** Check event logger
```bash
psql -U trading_user -d trading_bot_db << EOF
SELECT event_type, details, created_at
FROM trading_events
WHERE bot_name = 'coinbase_bot'
ORDER BY created_at DESC
LIMIT 20;
EOF
```

### Issue: "Database migration failed"
**Fix:**
```bash
# Check current migration status
alembic current

# View pending migrations
alembic pending

# Run upgrade
alembic upgrade head
```

---

## Safety Checklist Before Live Trading

- [ ] Database migration completed (`alembic upgrade 003`)
- [ ] `.env` file created with Coinbase credentials
- [ ] `config/bots.yaml` created with test allocation ($100-$500)
- [ ] Hard fence enabled (`type: "hard"`)
- [ ] Telegram notifications configured (for monitoring)
- [ ] Test on paper trading first (if Coinbase offers it)
- [ ] Local test run for 30 minutes without issues
- [ ] Verified signals being generated (`/metrics` shows activity)
- [ ] Checked database records match trades
- [ ] Monitored logs for errors 24 hours (if time permits)
- [ ] Small allocation confirmed (max $100-$500 for first week)

---

## First Week Monitoring Plan

**Day 1-2: Signal Generation Verification**
- Ensure bot is collecting bars and detecting signals
- Monitor via `/status` and `/metrics` every few hours
- Look for: bars received, filter statistics, signal generation rate

**Day 3-5: Live Trading Validation**
- Allow first few trades to execute
- Verify hard fence is working (check logs for fence checks)
- Monitor P&L via `/metrics`
- Check database: `SELECT * FROM trades WHERE bot_name = 'coinbase_bot'`

**Day 6-7: Pattern Analysis**
- Collect 7 days of data
- Calculate win rate (closed trades)
- Verify stops and takes-profit are triggering correctly
- Check for any stuck orders or hung positions

---

## Next Steps

1. **Set up environment** (prerequisites + .env)
2. **Create bots.yaml** (start with single $100 allocation)
3. **Run database migration** (`alembic upgrade 003`)
4. **Start local test** (30 minutes via `python -m trading_bot.main`)
5. **Verify signals** (check logs + Telegram + database)
6. **Scale if successful** (increase allocation after 1 week of positive data)
7. **Decision point** (after 1+ month): keep running, refine, or pivot strategy
