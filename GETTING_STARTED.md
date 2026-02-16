# Getting Started - Trading Bot

Complete guide to get your trading bot up and running with your father monitoring via Telegram.

## 5-Minute Quick Start

### 1. Prerequisites
```bash
# Install Docker Desktop from https://www.docker.com/products/docker-desktop
# Clone or download this trading bot project
cd trading-bot
```

### 2. Get API Keys
```bash
# Alpaca (for paper trading - risk-free testing)
# Sign up: https://app.alpaca.markets/
# Get keys from: API Keys section
```

### 3. Configure
```bash
cp .env.example .env
nano .env
# Add your ALPACA_API_KEY and ALPACA_SECRET_KEY
```

### 4. Start Trading Bot + Database
```bash
docker-compose -f docker/docker-compose.yml up -d
```

### 5. Check Status
```bash
docker-compose -f docker/docker-compose.yml ps
# Should show both 'postgres' and 'trading-bot' as running
```

**Done!** Trading bot is running with PostgreSQL database. 🚀

---

## Complete Setup (15 minutes)

### Step 1: Alpaca Setup (Paper Trading)

1. **Create Account**
   - Visit: https://app.alpaca.markets/
   - Sign up with email
   - Verify email

2. **Get API Keys**
   - Login to Alpaca
   - Go to: Dashboard → API Keys
   - Copy:
     - `ALPACA_API_KEY`
     - `ALPACA_SECRET_KEY`

3. **Important:**
   - **Paper trading** = Risk-free testing (recommended first)
   - **Live trading** = Real money (only after testing)

### Step 2: Telegram Setup (Monitoring)

1. **Create Telegram Bot**
   - Open Telegram
   - Search: `@BotFather`
   - Type: `/newbot`
   - Name it: "Trading Bot"
   - Username: "trading_bot_xyz"
   - Copy the **TOKEN**

2. **Get Chat ID**
   - Search for your bot in Telegram
   - Click "START"
   - Visit: `https://api.telegram.org/bot<TOKEN>/getUpdates`
   - Find: `"chat": {"id": YOUR_ID}`
   - Copy the **CHAT ID**

### Step 3: Configure Bot

```bash
# Copy template
cp .env.example .env

# Edit with your keys
nano .env
```

**Add your credentials:**
```env
# Alpaca (required)
ALPACA_API_KEY=your_api_key_here
ALPACA_SECRET_KEY=your_secret_key_here

# Trading
BROKER=alpaca
TRADING_ENV=paper

# Telegram (optional but recommended)
TELEGRAM_TOKEN=your_telegram_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Step 4: Start with Docker

```bash
# Start all services (bot + database)
docker-compose -f docker/docker-compose.yml up -d

# Check logs
docker-compose -f docker/docker-compose.yml logs -f trading-bot

# Should see:
# INFO | Trading Bot initialized
# INFO | ✅ Connected to PostgreSQL
# INFO | ✅ Telegram bot initialized
# INFO | Registered 4 health checks
```

### Step 5: Test in Telegram

In Telegram, message your bot:
```
/status  → Should show bot running + portfolio
/trades  → Should show recent trades
/metrics → Should show performance
```

### Step 6: Monitor Results

```bash
# View live logs
docker-compose -f docker/docker-compose.yml logs -f trading-bot

# Check database
docker exec trading-bot-db psql -U postgres -d trading_bot -c "SELECT * FROM trades LIMIT 5"

# View Telegram alerts in real-time
# (bot sends alerts when trades execute)
```

---

## What Gets Deployed

### Services

| Service | Purpose | Port |
|---------|---------|------|
| **trading-bot** | Main trading application | - |
| **postgres** | Database for trades/metrics | 5432 |
| **Telegram Bot** | Real-time monitoring | - |

### Data Storage

```
logs/
  └── trading_bot.log          # Bot logs

postgres_data/
  ├── trades                   # Entry/exit records
  ├── positions                # Open positions
  ├── performance_metrics      # Daily snapshots
  ├── trading_events           # Error logs
  └── health_checks            # Bot health status
```

### Key Features

- ✅ **Multi-broker support** (Alpaca + Coinbase)
- ✅ **Paper & live trading** (separate API keys)
- ✅ **Real-time monitoring** (Telegram alerts)
- ✅ **Trade persistence** (PostgreSQL)
- ✅ **Health checks** (auto-reconnect on failures)
- ✅ **4 strategies** (RSI-ATR, Mean Reversion, Momentum, Buy & Hold)

---

## Common Workflows

### Morning: Check Status

```bash
# In Telegram
/status
# See: Portfolio value, active trades, bot health

/trades
# See: Last 10 trades with P&L

/metrics
# See: Win rate, profit factor, performance
```

### Pause Before Important Event

```bash
# In Telegram
/pause
# Bot stops executing new trades
# Current positions stay open
```

### Resume Trading

```bash
# In Telegram
/resume
# Bot resumes executing trades
```

### View Logs

```bash
docker-compose -f docker/docker-compose.yml logs -f trading-bot

# Follow specific service
docker-compose -f docker/docker-compose.yml logs -f postgres
```

### Stop Everything

```bash
docker-compose -f docker/docker-compose.yml down

# Keep data (database persists)
# Docker images cached for faster restart
```

---

## Configuration Files

### .env (Your Secrets)

```env
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
TELEGRAM_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
```

⚠️ **Never commit this file to git!**

### config/strategies.yaml

```yaml
strategies:
  RSIATRTrendStrategy:
    enabled: true
    symbols:
      - SPY
      - AAPL
      - BTC/USD
    parameters:
      rsi_period: 14
      atr_period: 14
      min_atr: 0.5
      max_atr: 5.0
```

Edit to add/remove symbols or change strategy parameters.

### config/config.yml

```yaml
app:
  broker: alpaca
  trading_environment: paper
  log_level: INFO
  max_position_size: 0.1
  max_portfolio_risk: 0.02
```

---

## Paper Trading Walkthrough

### Week 1-2: Observation
- Let bot run 24/7 (during market hours)
- Monitor via Telegram alerts
- Check `/metrics` daily
- Look for win rate trends

### Week 2-3: Validation
- Review trade history: `/trades`
- Check performance: `/metrics`
- Look for consistency
- Validate profit factor >1.5

### Week 3+: Live Trading
**Only if paper trading shows:**
- ✅ Win rate >50%
- ✅ Profit factor >1.5
- ✅ Consistent results
- ✅ No major errors

**Then:**
1. Get live API keys from Alpaca
2. Create `.env.prod` with live keys
3. Start small: 1/10th normal position size
4. Monitor closely first week

---

## Troubleshooting

### "Bot won't start"

```bash
# Check logs
docker logs trading-bot

# Check PostgreSQL
docker logs trading-bot-db

# Restart
docker-compose -f docker/docker-compose.yml restart
```

### "Can't connect to database"

```bash
# Verify database is running
docker-compose -f docker/docker-compose.yml ps

# Check connection string
echo $DATABASE_URL
# Should be: postgresql://postgres:postgres@postgres:5432/trading_bot

# Test connection
docker exec trading-bot psql $DATABASE_URL -c "SELECT 1"
```

### "Telegram not sending messages"

```bash
# Check token is configured
docker exec trading-bot env | grep TELEGRAM

# Both should have values:
# TELEGRAM_TOKEN=...
# TELEGRAM_CHAT_ID=...

# Check logs for Telegram errors
docker logs trading-bot | grep -i telegram
```

### "No trades executing"

```bash
# Check if market is open (9:30 AM - 4:00 PM ET weekdays)
# Check strategy configuration
cat config/strategies.yaml | grep symbols

# Check logs for strategy errors
docker logs trading-bot | grep -i "strategy\|signal"
```

---

## Monitoring Your Father Can Do

### Via Telegram (Phone)

- **Command:** `/status` → See portfolio value
- **Command:** `/trades` → View recent trades
- **Command:** `/metrics` → Check performance
- **Command:** `/pause` → Stop trading
- **Command:** `/resume` → Resume trading
- **Alert:** Trade executed → Instant notification
- **Alert:** Connection error → Instant alert

### Via Terminal (You)

```bash
# Real-time logs
docker logs -f trading-bot

# Check database
docker exec trading-bot-db psql -U postgres -d trading_bot \
  -c "SELECT symbol, entry_price, exit_price, pnl_percent FROM trades ORDER BY entry_timestamp DESC LIMIT 10"

# Check health
docker exec trading-bot-db psql -U postgres -d trading_bot \
  -c "SELECT broker, strategy, is_healthy, connection_errors FROM health_checks"
```

---

## Next Steps

1. **Right now:** Follow "5-Minute Quick Start" above
2. **First run:** Let bot run for 1 hour, check `/trades` in Telegram
3. **First day:** Check `/metrics` a few times
4. **First week:** Let run 24/7, review daily performance
5. **Week 2+:** Decide on live trading (with small position size)

---

## Advanced Features (Optional)

### Switch to Coinbase (Crypto Only)

```env
BROKER=coinbase
TRADING_ENV=live  # No paper trading on Coinbase
COINBASE_API_KEY=your_key
COINBASE_SECRET_KEY=your_secret
COINBASE_PASSPHRASE=your_passphrase
```

### Custom Strategies

Edit `config/strategies.yaml` to:
- Add new symbols
- Change parameters
- Enable/disable strategies

### Database Backups

```bash
# Backup
docker exec trading-bot-db pg_dump -U postgres -d trading_bot > backup.sql

# Restore
docker exec -i trading-bot-db psql -U postgres -d trading_bot < backup.sql
```

---

## Documentation Map

| Document | Read When |
|----------|-----------|
| **This file** | You're here! 📍 |
| **MULTI_BROKER_SETUP.md** | Want to add Coinbase |
| **TELEGRAM_SETUP.md** | Telegram issues or advanced config |
| **DATABASE_SETUP.md** | Need database details |
| **DOCKER_SETUP.md** | Docker questions |
| **ALEMBIC_MIGRATIONS.md** | Adding schema changes |

---

## Support Checklist

- [ ] Alpaca account created & API keys obtained
- [ ] Telegram bot created & chat ID obtained
- [ ] `.env` file configured with credentials
- [ ] Docker Desktop installed & running
- [ ] `docker-compose up -d` successfully started
- [ ] Both `postgres` and `trading-bot` containers running
- [ ] Telegram bot receives startup message
- [ ] `/status` command works in Telegram
- [ ] Trades appear in database within first hour

---

## Key Facts

| Item | Value |
|------|-------|
| **Strategy** | RSI-ATR Trend (customizable) |
| **Timeframe** | 1-minute bars |
| **Brokers** | Alpaca (paper/live) + Coinbase (live only) |
| **Assets** | Stocks, crypto, forex, options |
| **Database** | PostgreSQL 15 |
| **Monitoring** | Telegram |
| **Deployment** | Docker |

---

## Ready to Go!

```bash
# 1. Copy template
cp .env.example .env

# 2. Add API keys
nano .env

# 3. Start everything
docker-compose -f docker/docker-compose.yml up -d

# 4. Monitor
docker-compose -f docker/docker-compose.yml logs -f trading-bot

# 5. Get alerts on Telegram
# Done! 🎉
```

**Questions?** Check the documentation or review the logs. Good luck! 🚀
