# Multi-Broker Support Guide

## Overview

Your TradingAutomata platform supports **multiple brokers** with the same strategy code. Switch between brokers without any code changes—just update your configuration!

**Supported Brokers:**
- **Alpaca**: Stocks, options, crypto, forex (paper & live)
- **Coinbase**: Crypto trading (live only)

**Use Case:**
- Test strategies on Alpaca (paper trading) with crypto
- Deploy to Coinbase (live) for real trading

---

## Broker Comparison

| Feature | Alpaca | Coinbase |
|---------|--------|----------|
| **Asset Classes** | Stocks, options, crypto, forex | Crypto only |
| **Paper Trading** | ✅ Yes | ❌ No |
| **Live Trading** | ✅ Yes | ✅ Yes |
| **API Quality** | Excellent | Good |
| **Crypto Selection** | 25+ assets | 100+ assets |
| **Execution Speed** | Fast | Fast |
| **Fees** | Competitive | Competitive |

---

## Configuration by Broker

### Alpaca (Paper Testing)

**Setup .env:**
```bash
BROKER=alpaca
TRADING_ENV=paper
ALPACA_API_KEY=pk_...
ALPACA_SECRET_KEY=...
```

**Features:**
✅ Test strategies without real money
✅ Trade stocks, options, crypto, forex
✅ Same code for paper and live

**Get Credentials:**
1. Go to https://app.alpaca.markets/
2. Sign up for paper trading (free)
3. Get API key from Settings > API Keys
4. Copy into .env file

### Coinbase (Live Crypto Trading)

**Setup .env:**
```bash
BROKER=coinbase
TRADING_ENV=live
COINBASE_API_KEY=...
COINBASE_SECRET_KEY=...
COINBASE_PASSPHRASE=...
```

**Features:**
✅ Live crypto trading
✅ 100+ cryptocurrencies
✅ High liquidity

**Get Credentials:**
1. Go to https://www.coinbase.com/settings/api
2. Create a new API key (use Coinbase Advanced API)
3. Give it "wallet:accounts:read" and "orders" permissions
4. **IMPORTANT**: Copy the passphrase somewhere safe (shown once)
5. Paste API key, secret key, and passphrase into .env

---

## Workflow: Test on Alpaca, Trade on Coinbase

### Phase 1: Test Strategy on Alpaca (Paper)

```bash
# Edit .env
BROKER=alpaca
TRADING_ENV=paper
ALPACA_API_KEY=pk_...
ALPACA_SECRET_KEY=...

# Run bot
docker-compose up
# or
python -m trading-automata.main
```

**What Happens:**
- Connect to Alpaca paper trading (simulated money)
- Test your strategy on real market data
- Monitor trading for 1-2 weeks
- Verify win rate > 50%
- Check logs for performance

### Phase 2: Deploy to Coinbase (Live)

Once strategy performs well on Alpaca:

```bash
# Edit .env
BROKER=coinbase
TRADING_ENV=live
COINBASE_API_KEY=...
COINBASE_SECRET_KEY=...
COINBASE_PASSPHRASE=...

# Same strategy, different broker!
docker-compose up
```

**Strategy Code: No Changes Needed!**

Your strategy works identically on both brokers because:
- Both implement the same `IBroker` interface
- The `TradingBot` class handles broker switching automatically
- Signal generation is broker-agnostic

---

## Configuration Examples

### Example 1: Alpaca Paper Trading (Testing)

```env
# .env
BROKER=alpaca
TRADING_ENV=paper
ALPACA_API_KEY=pk_test1234567890
ALPACA_SECRET_KEY=secret_test1234567890

LOG_LEVEL=INFO
MAX_POSITION_SIZE=0.1
MAX_PORTFOLIO_RISK=0.02
```

**Use Case:**
- Test new strategies
- Verify performance before live
- Low risk, learn as you go

### Example 2: Coinbase Live Trading

```env
# .env
BROKER=coinbase
TRADING_ENV=live
COINBASE_API_KEY=api_key_from_coinbase
COINBASE_SECRET_KEY=secret_key_from_coinbase
COINBASE_PASSPHRASE=passphrase_from_coinbase

LOG_LEVEL=INFO
MAX_POSITION_SIZE=0.05  # Conservative
MAX_PORTFOLIO_RISK=0.01  # 1% daily max loss
```

**Use Case:**
- Live crypto trading
- Use after paper testing
- Conservative position sizes

### Example 3: Multiple Strategies, Different Brokers

If you eventually want to run both simultaneously:

**deploy-alpaca-paper.env:**
```env
BROKER=alpaca
TRADING_ENV=paper
STRATEGY_CONFIG_PATH=config/strategies_alpaca.yaml
```

**deploy-coinbase-live.env:**
```env
BROKER=coinbase
TRADING_ENV=live
STRATEGY_CONFIG_PATH=config/strategies_coinbase.yaml
```

Run in separate containers:
```bash
docker-compose -f docker-compose.yml -e deploy-alpaca-paper.env up -d
docker-compose -f docker-compose.yml -e deploy-coinbase-live.env up -d
```

---

## Switching Brokers: Step by Step

### From Alpaca to Coinbase

**Step 1: Verify Strategy on Alpaca**
```bash
# .env file
BROKER=alpaca
TRADING_ENV=paper
ALPACA_API_KEY=pk_...
ALPACA_SECRET_KEY=...

# Run for 2+ weeks, verify >50% win rate
docker-compose logs -f | grep "Win rate\|Profit"
```

**Step 2: Get Coinbase Credentials**
- Go to https://www.coinbase.com/settings/api
- Create Advanced API key
- Save API key, secret, and passphrase

**Step 3: Update .env**
```bash
# Edit .env
BROKER=coinbase                 # ← Change broker
TRADING_ENV=live               # ← Switch to live
COINBASE_API_KEY=...           # ← Add credentials
COINBASE_SECRET_KEY=...
COINBASE_PASSPHRASE=...

# Keep Alpaca creds for data provider
ALPACA_API_KEY=pk_...
ALPACA_SECRET_KEY=...
```

**Step 4: Start Bot**
```bash
docker-compose restart
# or
docker-compose up
```

**That's it!** No code changes needed. Same strategy runs on Coinbase.

---

## Advanced: Custom Broker Implementation

To add a new broker (e.g., Interactive Brokers):

### 1. Create Broker Implementation

```python
# src/brokers/interactive_brokers.py
from .base import IBroker, Environment

class InteractiveBrokersBroker(IBroker):
    """Interactive Brokers implementation"""

    def connect(self) -> bool:
        # Implementation here
        pass

    def submit_order(self, symbol, qty, side, order_type, ...):
        # Implementation here
        pass

    # ... implement all IBroker methods
```

### 2. Update Factory

```python
# src/brokers/factory.py
from .interactive_brokers import InteractiveBrokersBroker

elif broker_type == 'interactive_brokers':
    return InteractiveBrokersBroker(
        account_id=config['account_id'],
        api_key=config['api_key'],
        # ...
    )
```

### 3. Update Settings

```python
# config/settings.py
ib_account_id: str = Field('', env='IB_ACCOUNT_ID')
ib_api_key: str = Field('', env='IB_API_KEY')
```

### 4. Use It

```bash
# .env
BROKER=interactive_brokers
IB_ACCOUNT_ID=...
IB_API_KEY=...
```

---

## Troubleshooting

### "Unsupported broker type"

**Error:**
```
ValueError: Unsupported broker type: my_broker
```

**Fix:**
- Check `BROKER=` in .env (must be `alpaca` or `coinbase`)
- Verify broker is registered in `BrokerFactory.create_broker()`

### "Missing credentials"

**Error:**
```
ValueError: Alpaca broker requires 'api_key' and 'secret_key' in config
```

**Fix:**
```bash
# Make sure .env has credentials
ALPACA_API_KEY=pk_...
ALPACA_SECRET_KEY=...
```

### "Failed to connect to Coinbase"

**Error:**
```
Failed to connect to Coinbase: Authentication failed
```

**Solutions:**
1. Verify API credentials are correct
2. Check passphrase matches exactly (case-sensitive)
3. Ensure API key has correct permissions:
   - `wallet:accounts:read`
   - `orders` (for trading)
4. Verify IP whitelist on Coinbase (if enabled)

### "Paper trading only works with Alpaca"

**Error:**
```
ValueError: Coinbase does not support paper trading
```

**Fix:**
Coinbase doesn't have a sandbox. You must:
1. Test strategies on Alpaca first (paper trading)
2. Use Coinbase only for live trading

---

## Best Practices

### Before Going Live with Coinbase

✅ **Do:**
- Test strategy on Alpaca paper for 2+ weeks
- Achieve >50% win rate on Alpaca
- Get profit factor >1.5
- Understand all entry/exit rules
- Have stop-losses in place
- Monitor closely first week on live

❌ **Don't:**
- Jump to Coinbase live without testing
- Use same position sizes as paper testing
- Trade with money you can't afford to lose
- Trade while sleeping (at least initially)

### Position Sizing

**Alpaca (Paper Testing):**
```yaml
position_size: 10  # Shares/units (doesn't matter, it's virtual)
```

**Coinbase (Live Trading):**
```yaml
position_size: 0.01  # Bitcoin units (real money!)
# Start small: 0.01 BTC ≈ $500
```

### Risk Management

**Alpaca Paper:**
```env
MAX_POSITION_SIZE=0.1   # Aggressive for learning
MAX_PORTFOLIO_RISK=0.05 # 5% daily max loss (okay for testing)
```

**Coinbase Live:**
```env
MAX_POSITION_SIZE=0.02  # Conservative
MAX_PORTFOLIO_RISK=0.01 # 1% daily max loss
```

---

## Monitoring Multiple Deployments

### Docker Compose with Multiple Brokers

**docker-compose-multi.yml:**
```yaml
version: '3.8'

services:
  trading-automata-alpaca:
    build: .
    env_file:
      - docker/.env.alpaca
    volumes:
      - ./logs/alpaca:/app/logs
    ports:
      - "8001:8000"

  trading-automata-coinbase:
    build: .
    env_file:
      - docker/.env.coinbase
    volumes:
      - ./logs/coinbase:/app/logs
    ports:
      - "8002:8000"
```

**Monitor Both:**
```bash
# View Alpaca logs
docker-compose -f docker-compose-multi.yml logs -f trading-automata-alpaca

# View Coinbase logs
docker-compose -f docker-compose-multi.yml logs -f trading-automata-coinbase
```

---

## Summary

| Scenario | Broker | Environment | Purpose |
|----------|--------|-------------|---------|
| Learning | Alpaca | paper | Free testing with real data |
| Testing | Alpaca | paper | Validate strategy before live |
| Live Trading (Crypto) | Coinbase | live | Real money trading |
| Testing with Real Money | Alpaca | live | If you prefer Alpaca for live |

**Key Point:** Same strategy code works everywhere. Just change config!

---

## Next Steps

1. **Test on Alpaca Paper:**
   ```bash
   BROKER=alpaca TRADING_ENV=paper python -m trading-automata.main
   ```

2. **Run for 2+ weeks:**
   - Monitor logs
   - Track performance
   - Adjust parameters if needed

3. **Get Coinbase Credentials:**
   - Go to https://www.coinbase.com/settings/api
   - Create Advanced API key

4. **Switch to Coinbase Live:**
   ```bash
   BROKER=coinbase TRADING_ENV=live COINBASE_API_KEY=... python -m trading-automata.main
   ```

**Ready to scale your trading across platforms!** 🚀
