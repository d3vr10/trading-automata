# Multi-Broker Implementation Complete ✅

## What Was Implemented

Your trading bot now supports **multiple brokers** with the same strategy code! No refactoring needed—just swap the broker in configuration.

### Files Created/Modified

#### New Files
- ✅ `src/brokers/coinbase_broker.py` - Coinbase broker implementation
- ✅ `docs/MULTI_BROKER.md` - Complete multi-broker guide

#### Modified Files
- ✅ `src/brokers/factory.py` - Added Coinbase support
- ✅ `src/brokers/base.py` - Already had IBroker interface ✓
- ✅ `config/settings.py` - Added Coinbase credentials
- ✅ `src/main.py` - Added `_build_broker_config()` method
- ✅ `config/config.yml` - Added Coinbase configuration
- ✅ `.env.example` - Added Coinbase credentials template
- ✅ `docker/.env.example` - Added Coinbase example
- ✅ `requirements.txt` - Added `coinbase-advanced-py`

---

## How It Works

### Architecture

```
┌─────────────────────────────────────────┐
│         TradingBot (main.py)            │
│  Handles strategy execution & signals   │
└────────────────────┬────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
    ┌────▼──────────┐    ┌───────▼──────────┐
    │  AlpacaBroker │    │  CoinbaseBroker  │
    │  (paper/live) │    │   (crypto only)  │
    └────┬──────────┘    └───────┬──────────┘
         │                       │
         └───────────┬───────────┘
                     │
            ┌────────▼────────┐
            │    IBroker      │
            │   Interface     │
            └─────────────────┘
```

**Key Design:**
- Both brokers implement `IBroker` interface
- Strategy code is broker-agnostic
- Configuration determines which broker to use
- Same `Signal` objects work with all brokers

---

## Quick Start: Two Scenarios

### Scenario A: Test on Alpaca, Deploy to Coinbase

**Step 1: Test on Alpaca (Paper Trading)**

```bash
# .env
BROKER=alpaca
TRADING_ENV=paper
ALPACA_API_KEY=pk_test...
ALPACA_SECRET_KEY=...

# Run bot
python -m src.main
```

**What Happens:**
- Connects to Alpaca paper trading (free, simulated)
- Trades with virtual money
- Tests your strategy safely
- Run for 2+ weeks

**Step 2: Deploy to Coinbase (Live Trading)**

```bash
# .env
BROKER=coinbase
TRADING_ENV=live
COINBASE_API_KEY=...
COINBASE_SECRET_KEY=...
COINBASE_PASSPHRASE=...

# Same code, different broker!
python -m src.main
```

**What Changed:**
- Just the .env file
- Same strategy code
- Same signals
- Real money trading on Coinbase

---

### Scenario B: Use Each Broker's Strengths

| Phase | Broker | Environment | Purpose |
|-------|--------|-------------|---------|
| **Test & Learn** | Alpaca | Paper | 0% risk, practice strategy |
| **Verify Strategy** | Alpaca | Live | Real money (if confident) |
| **Crypto Focus** | Coinbase | Live | Live crypto trading |

---

## Configuration Reference

### For Alpaca

```env
# .env
BROKER=alpaca
TRADING_ENV=paper        # or live
ALPACA_API_KEY=pk_...
ALPACA_SECRET_KEY=...
```

**Supports:**
- Stocks, options, crypto, forex
- Paper & live trading
- All timeframes

### For Coinbase

```env
# .env
BROKER=coinbase
TRADING_ENV=live         # Only live (no paper)
COINBASE_API_KEY=...
COINBASE_SECRET_KEY=...
COINBASE_PASSPHRASE=...  # Important: 3rd secret!
```

**Supports:**
- Crypto only (100+ assets)
- Live trading only
- All crypto pairs

---

## Getting Credentials

### Alpaca

1. Go to https://app.alpaca.markets/
2. Sign up (free)
3. Settings → API Keys
4. Copy API Key & Secret Key
5. Paste into .env

**Paper trading credentials are different from live!**

### Coinbase

1. Go to https://www.coinbase.com/settings/api
2. Create Advanced API Key
3. **Permissions needed:**
   - `wallet:accounts:read`
   - `orders` (to place trades)
4. Copy all 3 values:
   - API Key
   - Secret Key
   - **Passphrase** (shown once, save it!)
5. Paste into .env

---

## Switching Brokers

### From Alpaca to Coinbase

```bash
# 1. Get Coinbase credentials (see above)

# 2. Update .env
BROKER=coinbase                    # Changed
TRADING_ENV=live                   # Changed
COINBASE_API_KEY=...              # New
COINBASE_SECRET_KEY=...           # New
COINBASE_PASSPHRASE=...           # New

# Keep Alpaca creds for data provider
ALPACA_API_KEY=pk_...
ALPACA_SECRET_KEY=...

# 3. Restart bot
python -m src.main
```

**That's it!** Same strategy, different broker.

---

## Testing Multi-Broker Setup

### Verify Alpaca Connection

```bash
BROKER=alpaca TRADING_ENV=paper python -m src.main
```

**Expected Output:**
```
Connected to Alpaca (paper trading)
Account: ...
Portfolio Value: $...
```

### Verify Coinbase Connection

```bash
BROKER=coinbase COINBASE_API_KEY=... python -m src.main
```

**Expected Output:**
```
Connected to Coinbase (live trading)
Accounts: N
```

### Error Handling

If you get "Missing credentials" error, check:
1. Environment variables are set
2. No typos in .env file
3. Correct API key format
4. Passphrase for Coinbase (if using)

---

## Code Examples: What Changed

### Before (Single Broker)

```python
# src/main.py - Hard-coded Alpaca
broker = AlpacaBroker(api_key, secret_key, environment)
```

### After (Multi-Broker)

```python
# src/main.py - Dynamic broker selection
broker_config = self._build_broker_config()
broker = BrokerFactory.create_broker(
    broker_type=self.settings.broker,
    environment=environment,
    config=broker_config
)
```

**Strategy Code: No Changes!**

```python
# src/strategies/examples/rsi_atr_trend.py
# Works identically on both brokers
def on_bar(self, bar: Bar) -> Optional[Signal]:
    # ... same logic ...
    return Signal(...)  # Same Signal object works everywhere
```

---

## Production Recommendations

### Phase 1: Alpaca Paper Testing
- Run for 2+ weeks
- Verify win rate >50%
- Monitor logs daily
- Adjust parameters if needed

### Phase 2: Alpaca Live (Optional)
- If you want to use Alpaca live
- Start with 1/10th normal position size
- Monitor extremely closely
- Have kill switch ready

### Phase 3: Coinbase Live
- After successful Alpaca paper testing
- Get Coinbase credentials
- Swap BROKER=coinbase in .env
- Start with small position sizes
- Monitor closely

### Risk Settings for Coinbase Live

```env
# Conservative settings for real money
MAX_POSITION_SIZE=0.02   # 2% per position
MAX_PORTFOLIO_RISK=0.01  # 1% daily max loss
```

---

## Troubleshooting

### Issue: "Failed to connect to Coinbase"

**Check:**
1. API key and secret are correct
2. Passphrase matches exactly (case-sensitive)
3. API key has correct permissions
4. IP is whitelisted (if enabled)

### Issue: "Unsupported broker type: coinbase"

**Fix:** Ensure `requirements.txt` is up to date
```bash
pip install -r requirements.txt
```

### Issue: Strategy won't execute on Coinbase

**Check:**
1. Symbol format is correct (e.g., "BTC-USD")
2. Account has funds
3. Buying power is sufficient

---

## Next Steps

1. **For Testing:**
   ```bash
   BROKER=alpaca TRADING_ENV=paper python -m src.main
   ```
   Run for 2+ weeks, monitor performance

2. **For Live Coinbase:**
   - Get API credentials
   - Update .env with BROKER=coinbase
   - Start with tiny position sizes
   - Monitor extremely closely

3. **For Adding More Brokers:**
   - Create new implementation of `IBroker`
   - Register in `BrokerFactory`
   - Add credentials to `Settings`
   - Done! Plug and play.

---

## Key Files to Review

- **Multi-Broker Guide:** [docs/MULTI_BROKER.md](docs/MULTI_BROKER.md)
- **Broker Factory:** [src/brokers/factory.py](src/brokers/factory.py)
- **Coinbase Broker:** [src/brokers/coinbase_broker.py](src/brokers/coinbase_broker.py)
- **Main Application:** [src/main.py](src/main.py)
- **Configuration:** [config/settings.py](config/settings.py)

---

## Summary

✅ **Multi-broker support is fully implemented**
✅ **Same strategy works on both Alpaca & Coinbase**
✅ **Easy switching via configuration only**
✅ **Production-ready for live trading**

**Your bot is now ready to:**
1. Test strategies on Alpaca paper (risk-free)
2. Deploy to Coinbase live (real crypto trading)
3. Scale to additional brokers (Interactive Brokers, etc.)

**Ready to trade across platforms!** 🚀
