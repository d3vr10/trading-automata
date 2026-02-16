# Trading Bot

A production-grade Python trading bot for Alpaca's paper and live trading APIs. Features clean architecture with easy switching between paper and live trading environments.

## Features

- **Paper & Live Trading**: Seamless switching between trading environments via configuration
- **Docker Support**: Run with `docker-compose` for easy deployment
- **Flexible Configuration**: Support for config.yml + environment variable precedence
- **Modular Architecture**: Clean abstractions for brokers, data providers, and strategies
- **Strategy Framework**: Easy-to-implement base class for custom strategies
- **Production-Ready Strategies**: Generic RSI+ATR strategy (works on forex, stocks, crypto, commodities)
- **Portfolio Management**: Automatic position sizing and risk management
- **Order Execution**: Robust order management with status tracking
- **Extensible Design**: Add new brokers, data sources, and strategies without modifying core code

## Quick Start (Docker)

The fastest way to get started:

```bash
cd docker
cp .env.example .env
# Edit .env with your Alpaca API credentials
nano .env

docker-compose up
```

## Quick Start (Local)

### 1. Clone and Setup

```bash
cd trading-bot
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure

Choose one of these methods:

**Option A: Environment Variables Only**
```bash
export ALPACA_API_KEY="your_key"
export ALPACA_SECRET_KEY="your_secret"
python -m src.main
```

**Option B: .env File**
```bash
cp .env.example .env
# Edit .env with your credentials
python -m src.main
```

**Option C: config.yml + Environment Variables**
```bash
# Edit config/config.yml for defaults
# Create .env for overrides
python -m src.main
```

### 4. Enable Strategies

Edit `config/strategies.yaml`:

```yaml
strategies:
  # EUR/USD Professional Strategy (Recommended)
  - name: "eur_usd_rsi_atr"
    class: "EURUSDStrategy"
    enabled: true
    symbols:
      - "EURUSD"

  # Other example strategies
  - name: "mean_reversion_spy"
    class: "MeanReversionStrategy"
    enabled: false
    symbols:
      - "SPY"
```

### 5. Run the Bot

```bash
python -m src.main
```

Monitor logs:
```bash
tail -f logs/trading_bot.log
```

## Project Structure

```
trading-bot/
├── docker/                       # Docker setup
│   ├── Dockerfile              # Container image
│   ├── docker-compose.yml      # Docker Compose config
│   ├── .env.example            # Docker environment template
│   └── README.md               # Docker documentation
├── docs/                        # Documentation
│   ├── CONFIGURATION.md        # Configuration guide
│   └── RSI_ATR_STRATEGY.md     # Generic RSI+ATR strategy guide
├── src/
│   ├── main.py                 # Bot orchestrator
│   ├── brokers/
│   │   ├── base.py             # IBroker interface
│   │   ├── alpaca_broker.py    # Alpaca implementation
│   │   └── factory.py          # Broker factory
│   ├── data/
│   │   ├── base.py             # IDataProvider interface
│   │   ├── alpaca_data.py      # Alpaca data provider
│   │   └── models.py           # Data models
│   ├── strategies/
│   │   ├── base.py             # BaseStrategy class
│   │   ├── registry.py         # Strategy registry/loader
│   │   └── examples/
│   │       ├── buy_and_hold.py         # Buy and hold
│   │       ├── mean_reversion.py       # Mean reversion (Bollinger Bands)
│   │       ├── momentum.py             # Momentum strategy
│   │       └── rsi_atr_trend.py        # Generic RSI+ATR strategy ⭐
│   ├── portfolio/
│   │   └── manager.py          # Portfolio management
│   ├── execution/
│   │   └── order_manager.py    # Order execution
│   ├── monitoring/
│   │   └── logger.py           # Logging setup
│   └── utils/
│       └── exceptions.py       # Custom exceptions
├── config/
│   ├── settings.py             # Configuration management
│   ├── config.yml              # Application config (with defaults)
│   └── strategies.yaml         # Strategy configuration
├── tests/                      # Testing infrastructure
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── .env.example                # Environment template
├── requirements.txt            # Python dependencies
├── pyproject.toml             # Project configuration
├── README.md                   # This file
└── .gitignore                 # Git ignore rules
```

## Configuration Guide

The bot supports multiple configuration methods with environment variables taking precedence:

1. **Environment Variables** (highest priority)
2. **.env file**
3. **config.yml file**
4. **Built-in defaults**

See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for complete configuration guide.

### Configuration Priority Example

```yaml
# config/config.yml
app:
  trading_environment: paper
  log_level: DEBUG
```

```env
# .env
TRADING_ENV=live
```

```bash
# Result
export LOG_LEVEL=CRITICAL
python -m src.main
# trading_environment: live (from .env overrides config.yml)
# log_level: CRITICAL (from environment overrides .env)
```

## Generic RSI + ATR + EMA Strategy

A production-ready, **asset-agnostic strategy** combining RSI, ATR, and EMAs. Works on:
- 📈 Stocks (SPY, QQQ, etc.)
- 💱 Forex (EUR/USD, GBP/USD, etc.)
- 🪙 Crypto (BTC/USD, ETH/USD, etc.)
- 🛢️ Commodities (Gold, Oil, etc.)

**Features:**
- RSI-based overbought/oversold detection
- ATR-based volatility-adaptive position sizing
- EMA trend confirmation
- Built-in risk management (1:2 risk-reward)
- Expected: 52-58% win rate, 1.8-2.2 profit factor
- Configurable per asset class

**Setup Example (EUR/USD):**
```yaml
# config/strategies.yaml
- name: "rsi_atr_trend_eurusd"
  class: "RSIATRTrendStrategy"
  enabled: true
  symbols:
    - "EURUSD"
  parameters:
    rsi_period: 14
    position_size: 10  # Adjust per asset
```

**Or for Stocks (SPY):**
```yaml
- name: "rsi_atr_trend_spy"
  class: "RSIATRTrendStrategy"
  enabled: true
  symbols:
    - "SPY"
  parameters:
    position_size: 100  # Different size for stocks
```

See [docs/RSI_ATR_STRATEGY.md](docs/RSI_ATR_STRATEGY.md) for complete documentation and examples for different asset classes.

## Switching Between Paper and Live Trading

Change configuration without touching code:

```bash
# Paper trading
TRADING_ENV=paper python -m src.main

# Live trading (use live credentials!)
TRADING_ENV=live python -m src.main
```

Or edit `.env`:
```env
TRADING_ENV=paper  # or live
ALPACA_API_KEY=pk_...  # Paper or live key
ALPACA_SECRET_KEY=...
```

**⚠️ IMPORTANT**: When switching to live:
1. Use **live API credentials** (different from paper!)
2. Start with **1/10th normal position sizes**
3. Monitor **closely for errors**
4. Verify account has **proper funding**

## Creating Custom Strategies

Create a new strategy by inheriting from `BaseStrategy`:

```python
from src.strategies.base import BaseStrategy, Signal
from src.data.models import Bar, Quote
from typing import Optional, Dict, Any
from decimal import Decimal

class MyStrategy(BaseStrategy):
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.param = config.get('param', 'default')

    def on_bar(self, bar: Bar) -> Optional[Signal]:
        # Your logic here
        if some_condition:
            return Signal(
                symbol=bar.symbol,
                action='buy',
                quantity=Decimal('10'),
                confidence=0.9
            )
        return None

    def on_quote(self, quote: Quote) -> Optional[Signal]:
        # Optional: quote-based signals
        return None

    def validate_config(self) -> bool:
        return self.param is not None
```

Register your strategy in `src/main.py`:

```python
def _register_strategies(self) -> None:
    # ... existing registrations
    from src.strategies.examples.my_strategy import MyStrategy
    StrategyRegistry.register('MyStrategy', MyStrategy)
```

Add to `config/strategies.yaml`:

```yaml
strategies:
  - name: "my_strategy"
    class: "MyStrategy"
    enabled: true
    symbols:
      - "SPY"
    parameters:
      param: "value"
```

## Architecture Highlights

### Broker Abstraction

The `IBroker` interface allows switching between different brokers without changing strategy code:

```python
# Simple environment switching
environment = Environment.PAPER  # or Environment.LIVE
broker = BrokerFactory.create_broker('alpaca', environment, config)
```

### Strategy Pattern

Strategies are independent and pluggable:

```python
signal = strategy.on_bar(bar)  # Process data
portfolio_manager.execute_signal_if_valid(signal)  # Execute with constraints
```

### Portfolio Management

Orders are validated against portfolio constraints before execution:

- Checks available buying power for buy orders
- Verifies position exists for sell orders
- Enforces max position size constraints

## API Rate Limiting

Alpaca has rate limits. The bot:
- Uses efficient data requests
- Caches data when appropriate
- Respects API rate limits with sleep intervals

For high-frequency strategies, consider:
- Implementing local data caching
- Using websocket streams instead of polling
- Batching API calls

## Logging

Logs are written to:
- **Console**: INFO level and above
- **File**: DEBUG level and above (if `LOG_FILE` is configured)

Configure log level in `.env`:

```env
LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE=logs/trading_bot.log
```

## Monitoring

Monitor your bot with:

```bash
# Watch log file in real-time
tail -f logs/trading_bot.log

# Check Alpaca dashboard
# Visit https://app.alpaca.markets for paper trading
# Visit https://app.alpaca.markets for live trading (different account)
```

## Testing

Run unit tests:

```bash
pytest tests/
```

Run with coverage:

```bash
pytest tests/ --cov=src
```

## Common Issues

### Issue: "Failed to connect to broker"
- Check API credentials in `.env`
- Verify Alpaca API is accessible
- Check internet connection

### Issue: "Strategy config file not found"
- Verify `config/strategies.yaml` exists
- Check path in `.env` is correct

### Issue: Orders not executing
- Check account has buying power
- Verify position exists for sell orders
- Check portfolio constraints in `.env`

### Issue: "Market data unavailable"
- Verify market is open (trading only during market hours)
- Check symbol is valid for paper/live trading

## Best Practices

1. **Test in Paper Trading First**: Always test strategies in paper trading before going live
2. **Start Small**: Use small position sizes initially
3. **Monitor Closely**: Watch logs and portfolio while trading
4. **Use Stop Losses**: Implement stop-loss logic in strategies
5. **Diversify**: Don't concentrate all capital in one position
6. **Review Regularly**: Check performance metrics and adjust parameters

## Resources

- [Alpaca API Documentation](https://alpaca.markets/docs/)
- [Alpaca SDK (alpaca-py)](https://github.com/alpacahq/alpaca-py)
- [Trading Bot Architecture](docs/architecture.md)

## License

MIT

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review Alpaca API documentation
3. Check bot logs for error messages
4. Report issues with detailed logs and reproduction steps
