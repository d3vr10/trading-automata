# Quick Start: Deploy Multi-Bot Trading System to Coinbase

**Goal:** Get the system running on Coinbase in under 1 hour for your first test.

---

## 5-Minute Setup

### Step 1: Get Coinbase API Credentials (5 min)
1. Go to https://www.coinbase.com/settings/api
2. Click "Create API Key"
3. Select permissions: **Trading** only
4. Copy: `API Key`, `Secret Key`, `Passphrase` (passphrase shown once!)
5. Save these somewhere safe (we'll use them next)

### Step 2: Create `.env` File (2 min)
In the project root, create `.env`:

```bash
# Coinbase API
COINBASE_API_KEY="xxx"
COINBASE_SECRET_KEY="xxx"
COINBASE_PASSPHRASE="xxx"

# Database (PostgreSQL)
DATABASE_URL="postgresql://trading_user:password@localhost:5432/trading_bot_db"

# Telegram (optional - set to dummy values if not using)
TELEGRAM_BOT_TOKEN="dummy"
TELEGRAM_CHAT_ID="12345"

# Mode
BOT_MODE="multi"
```

### Step 3: Prepare Database (3 min)
```bash
# Ensure PostgreSQL is running
# Then run the migration:
alembic upgrade 003

# You should see:
# INFO [alembic.runtime.migration] Running upgrade ... add_bot_name
```

---

## 10-Minute Configuration

### Step 4: Create `config/bots.yaml` (5 min)

Copy and save this as `config/bots.yaml`:

```yaml
global:
  database_url: "${DATABASE_URL}"
  telegram_token: "${TELEGRAM_BOT_TOKEN}"
  telegram_chat_id: "${TELEGRAM_CHAT_ID}"
  log_level: "INFO"

bots:
  - name: "test_bot"
    enabled: true
    broker:
      type: "coinbase"
      api_key: "${COINBASE_API_KEY}"
      secret_key: "${COINBASE_SECRET_KEY}"
      passphrase: "${COINBASE_PASSPHRASE}"
    allocation:
      type: "dollars"
      amount: 100.00                  # $100 test budget
    fence:
      type: "hard"
    risk:
      stop_loss_pct: 2.0
      take_profit_pct: 6.0
      max_position_size: 50.00
      max_portfolio_risk: 5.0
    trade_frequency:
      poll_interval_minutes: 1
    strategy_config: "config/strategies.yaml"
    data_provider:
      type: "alpaca"
      api_key: "${ALPACA_API_KEY}"
      secret_key: "${ALPACA_SECRET_KEY}"
```

### Step 5: Verify Configuration (2 min)
```bash
python -c "from trading_bot.config.loader import load_bot_configs; c = load_bot_configs(); print(f'✓ Loaded {len(c.bots)} bot(s)')"

# Output should be:
# ✓ Loaded 1 bot(s)
```

### Step 6: Verify Dependencies (3 min)
```bash
pip install -r requirements.txt

# Test imports:
python -c "from trading_bot.orchestration.orchestrator import BotOrchestrator; print('✓ Ready')"
```

---

## Start the Bot (1 minute)

```bash
python -m trading_bot.main
```

**Expected output (first 30 seconds):**
```
Multi-bot mode detected - using BotOrchestrator
[2026-02-22 14:30:15] Setting up BotOrchestrator...
[2026-02-22 14:30:16] Initialized 1 bot(s)
[2026-02-22 14:30:16] [test_bot] Connecting to Coinbase broker...
[2026-02-22 14:30:18] [test_bot] Connected to Coinbase broker successfully
[2026-02-22 14:30:19] [test_bot] Registered 4 strategies
[2026-02-22 14:30:19] [test_bot] Starting trading loop...
[2026-02-22 14:30:20] [test_bot] 10 bars received for BTC-USD
[2026-02-22 14:30:21] [test_bot] 10 bars received for ETH-USD
```

✅ **If you see bars being received, your bot is working!**

---

## Monitor Your Bot

### In Another Terminal:

```bash
# Check database for signals
psql -U trading_user -d trading_bot_db << EOF
SELECT event_type, COUNT(*) FROM trading_events
WHERE bot_name = 'test_bot'
GROUP BY event_type
ORDER BY COUNT(*) DESC;
EOF

# Expected output after 5-10 minutes:
#  event_type      | count
# -----------------+-------
#  bar_received    |  100
#  filter_checked  |   80
#  signal_check    |   20
```

### Check Trades:
```bash
psql -U trading_user -d trading_bot_db << EOF
SELECT symbol, action, quantity, price, created_at
FROM trades
WHERE bot_name = 'test_bot'
ORDER BY created_at DESC
LIMIT 10;
EOF
```

### View Logs:
```bash
tail -f logs/trading_bot.log | grep "test_bot"
```

---

## First 24 Hours: What to Expect

### Hour 1:
- ✅ Bot connects to Coinbase
- ✅ Bars being received
- ✅ No errors in logs
- ❓ Maybe first signal (depends on market conditions)

### Hours 2-6:
- ✅ Multiple bars received
- ✅ Filter activity visible in event log
- ❓ 1-3 signals generated (if conditions align)
- ✅ Orders executed (if signals triggered)

### Hours 6-24:
- ✅ Steady bar flow
- ✅ 5-20+ trades executed (strategy-dependent)
- ✅ Database growing with trades/events
- ✅ Health checks saved every 5 minutes

### If NO signals after 24 hours:
This is OK for some strategies. Check:
```bash
# Verify strategy is enabled and receiving bars
psql -U trading_user -d trading_bot_db << EOF
SELECT
  DATE_TRUNC('hour', created_at) as hour,
  event_type,
  COUNT(*) as count
FROM trading_events
WHERE bot_name = 'test_bot'
GROUP BY hour, event_type
ORDER BY hour DESC, event_type;
EOF

# If bars_received > 100 but no signals:
# - Filters too strict (min_volume, volatility)
# - Strategy conditions not met (normal in low-volatility markets)
# - Check details in event log for why filters rejected
```

---

## Telegram Monitoring (Optional but Recommended)

To get trading alerts in Telegram:

### 1. Create Telegram Bot:
- Message [@BotFather](https://t.me/botfather) on Telegram
- Command: `/newbot`
- Name: "MyTradingBot" (any name)
- Username: "my_trading_bot_XXXXX" (must be unique)
- Copy the token: `123:ABC...`

### 2. Get Your Chat ID:
- Message [@userinfobot](https://t.me/userinfobot)
- It replies with your chat ID (numeric)

### 3. Update `.env`:
```bash
TELEGRAM_BOT_TOKEN="123:ABC..."
TELEGRAM_CHAT_ID="123456789"
```

### 4. Restart Bot:
```bash
# Ctrl+C to stop current bot
python -m trading_bot.main

# Should see: [test_bot] Telegram notifications enabled
```

### 5. Try Commands in Telegram:
```
/status              # Get bot status
/bots                # List all bots with balance
/metrics test_bot    # P&L chart
/trades test_bot open # Show open positions
/pause_bot test_bot  # Pause trading
/resume_bot test_bot # Resume trading
```

---

## Common Issues & Fixes

| Issue | Fix |
|-------|-----|
| `Cannot connect to Coinbase` | Check API credentials in `.env`, verify firewall |
| `No signals after 24h` | Check event log for filter rejections, may be normal |
| `Database error` | Verify DATABASE_URL, ensure PostgreSQL is running |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` again |
| `config/bots.yaml not found` | Verify file exists in project root `config/` directory |

---

## Next Steps (After 24 Hours)

### Option A: Continue as-is
- Leave bot running
- Monitor daily via Telegram or database
- Plan next move after 7+ days of data

### Option B: Add More Capital
- Update `allocation.amount` in `config/bots.yaml`
- Increase by 50% each week (e.g., $100 → $150 → $225)
- Watch for issues at each step

### Option C: Add Second Bot
- Copy bot config in `config/bots.yaml`
- Rename to different name (e.g., "test_bot_2")
- Different strategy or same strategy on different symbols
- Both run simultaneously with independent capital

### Option D: Scale to Live Trading
- After 7-14 days of positive results
- **INCREASE ALLOCATION TO $500-$1000 ONLY AFTER**:
  - ✅ Win rate confirmed > 50%
  - ✅ Profit factor > 1.0
  - ✅ No consecutive losing periods > 3 days
  - ✅ Hard fence never triggered (no attempted over-allocation)

---

## Understanding the System

### Architecture
```
BotOrchestrator (1 instance)
  ├─ PostgreSQL (1 database, multi-bot)
  ├─ Telegram Bot (1 instance, all bots)
  └─ BotInstance x N (1 per bot in config/bots.yaml)
       ├─ Coinbase Broker (1 per bot)
       ├─ VirtualPortfolioManager (1 per bot)
       ├─ Strategies (multiple per bot)
       └─ EventLogger (shared, filtered by bot_name)
```

### Key Concepts

**Allocation**: Virtual capital pool for each bot
- Hard fence: Cannot spend more than allocated
- Soft fence: Can overage with warning (not recommended)

**Virtual Balance**: How much of allocation is still available
- Virtual spent: Amount used in buy orders
- Virtual proceeds: Amount received from sell orders
- Available: allocated_capital - spent + proceeds

**Signals**: Trading recommendation from strategy
- Includes: buy/sell, symbol, quantity, confidence, metadata
- Risk controls auto-injected: SL%, TP%
- Hard fence checks before execution

**Health Checks**: Bot status saved every 5 minutes
- HEALTHY: All systems working
- DEGRADED: Minor issues (retry pending)
- ERROR: Critical failure (check logs)

---

## Troubleshooting Command Reference

```bash
# Check if bot is running
ps aux | grep "python -m trading_bot.main"

# View recent errors
tail -n 50 logs/trading_bot.log | grep ERROR

# Check database connection
psql -U trading_user -d trading_bot_db -c "SELECT 1"

# View all trades
psql -U trading_user -d trading_bot_db \
  -c "SELECT * FROM trades WHERE bot_name='test_bot' ORDER BY created_at DESC LIMIT 20"

# View recent events
psql -U trading_user -d trading_bot_db \
  -c "SELECT event_type, details FROM trading_events WHERE bot_name='test_bot' ORDER BY created_at DESC LIMIT 50"

# Check bot health
psql -U trading_user -d trading_bot_db \
  -c "SELECT * FROM health_checks WHERE bot_name='test_bot' ORDER BY created_at DESC LIMIT 10"

# Restart bot
# 1. Press Ctrl+C in bot terminal
# 2. Run: python -m trading_bot.main
```

---

## Success Checklist

After running for 24 hours, verify:

- [ ] Bot starts without errors
- [ ] Broker connects successfully
- [ ] Bars received (10+ entries in events table)
- [ ] Strategies loaded without errors
- [ ] No crash over 24 hours
- [ ] At least some filter activity in event log
- [ ] Telegram notifications received (if enabled)

**All checked?** → System is working! ✅

---

## What Now?

You have three paths forward:

### Path 1: Prove Effectiveness (Recommended)
- Run bot for 1-4 weeks
- Collect performance data
- Validate win rate > 50%, profit factor > 1.0
- **Decision milestone:** Decide commercialization strategy (open-source / product / hybrid)

### Path 2: Scale Up
- After 1 week positive results
- Increase allocation by 50%
- Monitor for issues
- Repeat weekly if profitable

### Path 3: Iterate Strategy
- If not profitable after 1 week
- Adjust risk parameters (wider SL%, lower TP%)
- Try different strategy (e.g., conservative vs momentum)
- Run another 1-week test

---

## Need Help?

1. **Check logs**: `tail -f logs/trading_bot.log`
2. **Check event log**: Query `trading_events` table
3. **Check database**: Use `psql` to inspect trades/positions
4. **Read docs**:
   - Full deployment guide: [COINBASE_DEPLOYMENT_GUIDE.md](COINBASE_DEPLOYMENT_GUIDE.md)
   - Testing checklist: [TESTING_CHECKLIST.md](TESTING_CHECKLIST.md)
   - Example configs: [config/example-bots-coinbase.yaml](config/example-bots-coinbase.yaml)

---

**Status:** Your multi-bot trading system is ready to run. Deploy and start gathering data! 🚀
