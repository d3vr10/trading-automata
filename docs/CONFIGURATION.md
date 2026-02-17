# Configuration Guide

This document explains how to configure the trading bot using configuration files and environment variables.

## Configuration Hierarchy

The bot loads configuration in the following order, with each level overriding the previous:

1. **Defaults** (hardcoded in code)
2. **config.yml** (optional YAML configuration file)
3. **.env file** (environment variables loaded from .env)
4. **OS Environment Variables** (highest priority)

This means: **OS Environment Variables > .env file > config.yml > Defaults**

## Quick Reference

### Minimal Configuration (Docker)

```bash
# .env or docker/.env
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
```

### Full Configuration (config.yml)

```yaml
app:
  trading_environment: paper
  broker: alpaca
  log_level: INFO
  max_position_size: 0.1
  max_portfolio_risk: 0.02
```

## Configuration Methods

### Method 1: Environment Variables Only

Set environment variables:

```bash
export ALPACA_API_KEY="your_key"
export ALPACA_SECRET_KEY="your_secret"
export TRADING_ENV="paper"
export LOG_LEVEL="INFO"
```

Run bot:

```bash
python -m trading_bot.main
```

### Method 2: .env File

Create `.env` in project root:

```env
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
TRADING_ENV=paper
LOG_LEVEL=INFO
```

The bot automatically loads this file.

### Method 3: config.yml File

Create `config/config.yml`:

```yaml
app:
  alpaca_api_key: your_key
  alpaca_secret_key: your_secret
  trading_environment: paper
  log_level: INFO
```

### Method 4: Combination (Recommended)

Best practice for production:

1. **config.yml**: Store defaults and non-sensitive configuration
2. **.env**: Store development secrets
3. **Environment Variables**: Override for specific deployments

Example `config.yml`:

```yaml
app:
  trading_environment: paper
  log_level: INFO
  max_position_size: 0.1
  strategy_config_path: config/strategies.yaml
```

Example `.env`:

```env
ALPACA_API_KEY=dev_key
ALPACA_SECRET_KEY=dev_secret
```

Environment variable override:

```bash
TRADING_ENV=live python -m trading_bot.main
```

## Configuration Options

### Core Settings

| Key | Environment Variable | Type | Default | Description |
|-----|----------------------|------|---------|-------------|
| `alpaca_api_key` | `ALPACA_API_KEY` | string | *required* | Alpaca API key |
| `alpaca_secret_key` | `ALPACA_SECRET_KEY` | string | *required* | Alpaca secret key |
| `trading_environment` | `TRADING_ENV` | string | `paper` | `paper` or `live` |
| `broker` | `BROKER` | string | `alpaca` | Broker type |

### Logging

| Key | Environment Variable | Type | Default | Description |
|-----|----------------------|------|---------|-------------|
| `log_level` | `LOG_LEVEL` | string | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `log_file` | `LOG_FILE` | string | `logs/trading_bot.log` | Path to log file (optional) |

### Strategy Configuration

| Key | Environment Variable | Type | Default | Description |
|-----|----------------------|------|---------|-------------|
| `strategy_config_path` | `STRATEGY_CONFIG_PATH` | string | `config/strategies.yaml` | Path to strategies YAML |
| `config_file_path` | `CONFIG_FILE_PATH` | string | `config/config.yml` | Path to main config file |

### Risk Management

| Key | Environment Variable | Type | Default | Description |
|-----|----------------------|------|---------|-------------|
| `max_position_size` | `MAX_POSITION_SIZE` | float | `0.1` | Max position % of portfolio (0-1) |
| `max_portfolio_risk` | `MAX_PORTFOLIO_RISK` | float | `0.02` | Max daily loss % (0-1) |

## Docker Configuration

### Using docker-compose

Create `docker/.env`:

```env
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
TRADING_ENV=paper
LOG_LEVEL=INFO
```

Run:

```bash
docker-compose -f docker/docker-compose.yml up
```

### Environment Variable Precedence in Docker

The `docker-compose.yml` loads variables in this order:

1. `.env` file in same directory
2. Environment variables passed to docker-compose
3. Hardcoded defaults in compose file

Example override:

```bash
TRADING_ENV=live docker-compose -f docker/docker-compose.yml up
```

## Strategy Configuration

Strategies are configured in `config/strategies.yaml`:

```yaml
strategies:
  - name: "eur_usd_rsi_atr"
    class: "EURUSDStrategy"
    enabled: true
    symbols:
      - "EURUSD"
    parameters:
      rsi_period: 14
      rsi_oversold: 30
      rsi_overbought: 70
      # ... more parameters
```

Each strategy can have:

- **name**: Unique strategy identifier
- **class**: Strategy class name (must be registered)
- **enabled**: Whether to load this strategy
- **symbols**: List of symbols to trade
- **parameters**: Strategy-specific configuration

## Paper vs Live Trading

### Paper Trading (Default)

```env
TRADING_ENV=paper
ALPACA_API_KEY=pk_...  # Paper trading key
ALPACA_SECRET_KEY=...   # Paper trading secret
```

### Live Trading

```env
TRADING_ENV=live
ALPACA_API_KEY=pk_...  # LIVE trading key
ALPACA_SECRET_KEY=...   # LIVE trading secret
```

**CRITICAL**: Different API credentials are needed for live trading. Never use live credentials in paper mode or vice versa.

## Configuration Validation

The bot validates configuration on startup:

```bash
python -m trading_bot.main
```

If configuration is invalid, you'll see errors like:

```
ValueError: Invalid trading_environment: invalid_env. Must be 'paper' or 'live'.
ValueError: max_position_size must be between 0 and 1, got 1.5
```

## Environment-Specific Configurations

### Development

`.env`:
```env
ALPACA_API_KEY=pk_...
ALPACA_SECRET_KEY=...
TRADING_ENV=paper
LOG_LEVEL=DEBUG
LOG_FILE=logs/trading_bot.log
```

### Testing

```bash
TRADING_ENV=paper \
LOG_LEVEL=INFO \
STRATEGY_CONFIG_PATH=config/strategies.test.yaml \
python -m trading_bot.main
```

### Production

Environment variables (no .env files):

```bash
export ALPACA_API_KEY="..."
export ALPACA_SECRET_KEY="..."
export TRADING_ENV="live"
export LOG_LEVEL="INFO"
export MAX_POSITION_SIZE="0.05"  # More conservative
```

## Configuration Merging Example

Given:

**config.yml:**
```yaml
app:
  trading_environment: paper
  log_level: DEBUG
  max_position_size: 0.15
```

**.env:**
```env
TRADING_ENV=live
MAX_POSITION_SIZE=0.1
```

**OS Environment:**
```bash
export LOG_LEVEL=CRITICAL
```

**Result:**
- `trading_environment`: `live` (from .env overrides config.yml)
- `log_level`: `CRITICAL` (from OS env overrides .env)
- `max_position_size`: `0.1` (from .env overrides config.yml)
- API keys: from config.yml or .env

## Troubleshooting Configuration

### Config file not found

```
ValueError: Strategy config file not found: config/strategies.yaml
```

**Solution:**
```bash
ls config/strategies.yaml  # Verify file exists
STRATEGY_CONFIG_PATH=./config/strategies.yaml python -m trading_bot.main
```

### Missing required settings

```
ValueError: 1 validation error for Settings
alpaca_api_key
  Field required (type=value_error.missing)
```

**Solution:**
```bash
export ALPACA_API_KEY="your_key"
export ALPACA_SECRET_KEY="your_secret"
```

### Invalid setting values

```
ValueError: Invalid trading_environment: test. Must be 'paper' or 'live'.
```

**Solution:**
```bash
export TRADING_ENV=paper  # Only 'paper' or 'live'
```

## Best Practices

1. **Never commit .env files to git**
   ```bash
   echo ".env" >> .gitignore
   ```

2. **Use config.yml for non-sensitive defaults**
   ```yaml
   app:
     trading_environment: paper
     log_level: INFO
   ```

3. **Use environment variables for secrets**
   ```bash
   export ALPACA_API_KEY="..."
   export ALPACA_SECRET_KEY="..."
   ```

4. **Use different credentials for paper vs live**
   - Paper: `TRADING_ENV=paper ALPACA_API_KEY=pk_...`
   - Live: `TRADING_ENV=live ALPACA_API_KEY=sk_...`

5. **Validate on startup**
   ```bash
   python -m trading_bot.main  # Will fail if config is invalid
   ```

6. **Use specific config paths for different environments**
   ```bash
   CONFIG_FILE_PATH=config/config.prod.yml python -m trading_bot.main
   ```

## Configuration Files Reference

- **config/config.yml**: Main application configuration
- **config/strategies.yaml**: Strategy definitions
- **.env**: Environment variables (local development)
- **.env.example**: Example environment variables
- **docker/.env.example**: Docker environment example

## Environment Variable Names

| Configuration Key | Environment Variable |
|-------------------|-----------------------|
| alpaca_api_key | ALPACA_API_KEY |
| alpaca_secret_key | ALPACA_SECRET_KEY |
| trading_environment | TRADING_ENV |
| broker | BROKER |
| log_level | LOG_LEVEL |
| log_file | LOG_FILE |
| strategy_config_path | STRATEGY_CONFIG_PATH |
| config_file_path | CONFIG_FILE_PATH |
| max_position_size | MAX_POSITION_SIZE |
| max_portfolio_risk | MAX_PORTFOLIO_RISK |
