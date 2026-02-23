# Trading Bot

A production-grade Python trading bot with **multi-broker support** (Alpaca & Coinbase). Features clean architecture with strategy framework, event logging, database persistence, and Docker deployment.

## Features

- **Multi-Broker Support**: Trade on Alpaca (paper/live) and Coinbase (live crypto) with same strategy code
- **Paper & Live Trading**: Seamless switching between trading environments via configuration
- **Event Logging**: Track all trading decisions (bars, filters, signals, orders) for troubleshooting
- **PostgreSQL Database**: Persistent storage of trades, positions, health checks, and events
- **Docker Support**: Full stack (bot + PostgreSQL) with `docker-compose` for easy deployment
- **CLI Tools**: Command-line interface for checking status, trades, metrics, and events
- **Flexible Configuration**: Support for config.yml + environment variable precedence
- **Strategy Framework**: Easy-to-implement base class for custom strategies
- **Production-Ready Strategies**: Generic RSI+ATR strategy (works on forex, stocks, crypto, commodities)
- **Filter System**: Volatility and liquidity filters to control when trades happen
- **Portfolio Management**: Automatic position sizing and risk management
- **Order Execution**: Robust order management with status tracking
- **Health Monitoring**: Automatic health checks and reconnection logic
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
python -m trading_bot.main
```

**Option B: .env File**
```bash
cp .env.example .env
# Edit .env with your credentials
python -m trading_bot.main
```

**Option C: config.yml + Environment Variables**
```bash
# Edit config/config.yml for defaults
# Create .env for overrides
python -m trading_bot.main
```

### 4. Configure Database (Optional)

```bash
# Create PostgreSQL database
createdb trading_bot

# Run migrations
alembic upgrade head
```

### 5. Enable Strategies

Edit `config/strategies.yaml`:

```yaml
strategies:
  # RSI+ATR Strategy - Works on Stocks, Forex, Crypto
  - name: "rsi_atr_trend_spy"
    class: "RSIATRTrendStrategy"
    enabled: true
    symbols:
      - "SPY"  # Paper trading: stocks work, forex requires live account
    parameters:
      rsi_period: 14
      position_size: 100

  # Other example strategies
  - name: "mean_reversion_spy"
    class: "MeanReversionStrategy"
    enabled: false
    symbols:
      - "SPY"
```

**Note**: Alpaca paper trading supports stocks (SPY, QQQ, AAPL, etc.). Forex and crypto require a live account.

### 6. Run the Bot

```bash
python -m trading_bot.main
```

Monitor logs:
```bash
tail -f logs/trading_bot.log
```

Check bot status with CLI:
```bash
python -m trading_bot.cli status              # Overall status
python -m trading_bot.cli trades              # Trade history
python -m trading_bot.cli events --limit 50   # Recent events
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
│   ├── RSI_ATR_STRATEGY.md     # Generic RSI+ATR strategy guide
│   ├── FILTERS.md              # Volatility & liquidity filters
│   ├── MULTI_BROKER.md         # Alpaca & Coinbase support
│   ├── DATABASE_SETUP.md       # PostgreSQL configuration
│   ├── DATABASE_INTEGRATION.md # Database & health checks
│   ├── ALEMBIC_MIGRATIONS.md   # Database schema migrations
│   ├── DOCKER_SETUP.md         # Docker Compose deployment
│   ├── TELEGRAM_SETUP.md       # Telegram notifications
│   └── EUR_USD_STRATEGY.md     # EUR/USD strategy example
├── trading_bot/                 # Main package
│   ├── main.py                 # Bot orchestrator
│   ├── cli.py                  # Command-line interface
│   ├── brokers/
│   │   ├── base.py             # IBroker interface
│   │   ├── alpaca_broker.py    # Alpaca implementation
│   │   ├── coinbase_broker.py  # Coinbase implementation
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
│   ├── database/
│   │   ├── health.py           # Health monitoring
│   │   ├── init.py             # Database initialization
│   │   └── connection.py       # Database connection management
│   ├── monitoring/
│   │   ├── logger.py           # Logging setup
│   │   └── event_logger.py     # Event logging and tracking
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
python -m trading_bot.main
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

**Setup Example (Stocks - Paper Trading):**
```yaml
# config/strategies.yaml
- name: "rsi_atr_trend_spy"
  class: "RSIATRTrendStrategy"
  enabled: true
  symbols:
    - "SPY"   # Works with Alpaca paper trading
  parameters:
    rsi_period: 14
    position_size: 100  # Shares (stocks)
    filters:
      min_atr: 0.50
      max_atr: 5.00
      min_volume: 1000000
```

**Setup Example (Forex - Live Trading):**
```yaml
# config/strategies.yaml
- name: "rsi_atr_trend_eurusd"
  class: "RSIATRTrendStrategy"
  enabled: true
  symbols:
    - "EUR/USD"   # Requires live account (not available in paper trading)
  parameters:
    rsi_period: 14
    position_size: 100000  # Units (forex)
    filters:
      min_atr: 30    # pips
      max_atr: 200   # pips
      min_volume: 500000
```

**Note**: Alpaca paper trading supports stocks only. Forex, crypto, and commodities require a live trading account.

See [docs/RSI_ATR_STRATEGY.md](docs/RSI_ATR_STRATEGY.md) for complete documentation and examples for different asset classes.

## Switching Between Paper and Live Trading

Change configuration without touching code:

```bash
# Paper trading
TRADING_ENV=paper python -m trading_bot.main

# Live trading (use live credentials!)
TRADING_ENV=live python -m trading_bot.main
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
from trading_bot.strategies.base import BaseStrategy, Signal
from trading_bot.data.models import Bar, Quote
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
    from trading_bot.strategies.examples.my_strategy import MyStrategy
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

### Real-Time Logs

```bash
# Watch log file in real-time
tail -f logs/trading_bot.log
```

### CLI Commands

The bot includes a command-line interface for checking status and debugging:

```bash
# Overall bot status
python -m trading_bot.cli status

# View recent trades
python -m trading_bot.cli trades --limit 10

# View trading events and decisions
python -m trading_bot.cli events --limit 50

# View specific event types
python -m trading_bot.cli events --type BAR_RECEIVED --symbol SPY

# View performance metrics
python -m trading_bot.cli metrics

# Check database health
python -m trading_bot.cli health
```

### Web Dashboards

- **Alpaca Paper Trading**: https://app.alpaca.markets (paper account)
- **Alpaca Live Trading**: https://app.alpaca.markets (live account - different credentials)
- **Coinbase**: https://advanced.coinbase.com (for live crypto trading)

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

## Documentation

Complete guides for all features:

**Getting Started:**
- **[CONFIGURATION.md](docs/CONFIGURATION.md)** - Configuration methods, environment variables, priorities
- **[DOCKER_SETUP.md](docs/DOCKER_SETUP.md)** - Docker Compose deployment guide

**Operations & Monitoring:**
- **[BOT_MONITORING.md](docs/BOT_MONITORING.md)** - Bot lifecycle, startup phases, health monitoring, troubleshooting logs
- **[DATABASE_SETUP.md](docs/DATABASE_SETUP.md)** - PostgreSQL installation and configuration
- **[TELEGRAM_SETUP.md](docs/TELEGRAM_SETUP.md)** - Telegram bot notifications

**Strategies & Trading:**
- **[RSI_ATR_STRATEGY.md](docs/RSI_ATR_STRATEGY.md)** - Generic RSI+ATR strategy for any asset class
- **[EUR_USD_STRATEGY.md](docs/EUR_USD_STRATEGY.md)** - Example EUR/USD trading strategy
- **[FILTERS.md](docs/FILTERS.md)** - Volatility and liquidity filters configuration

**Architecture & Development:**
- **[MULTI_BROKER.md](docs/MULTI_BROKER.md)** - Alpaca and Coinbase setup and usage
- **[DATABASE_INTEGRATION.md](docs/DATABASE_INTEGRATION.md)** - Database schema, health checks
- **[ALEMBIC_MIGRATIONS.md](docs/ALEMBIC_MIGRATIONS.md)** - Database migrations and schema versioning

## External Resources

- [Alpaca API Documentation](https://alpaca.markets/docs/)
- [Alpaca SDK (alpaca-py)](https://github.com/alpacahq/alpaca-py)
- [Coinbase Advanced Trading API](https://docs.cdp.coinbase.com/advanced-trade/docs/welcome)

## License

MIT

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review Alpaca API documentation
3. Check bot logs for error messages
4. Report issues with detailed logs and reproduction steps
