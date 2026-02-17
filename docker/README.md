# Docker Setup for Trading Bot

This directory contains Docker configuration files for running the trading bot in a containerized environment.

## Files

- **Dockerfile**: Container image definition
- **docker-compose.yml**: Multi-container orchestration (currently single service)
- **.env.example**: Example environment variables for Docker

## Quick Start

### 1. Build the Docker Image

```bash
cd docker
docker-compose build
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your Alpaca API credentials and settings
nano .env
```

### 3. Run the Trading Bot

```bash
docker-compose up
```

To run in the background:

```bash
docker-compose up -d
```

### 4. View Logs

```bash
# Real-time logs
docker-compose logs -f

# Last 100 lines
docker-compose logs --tail=100

# Specific service
docker-compose logs -f trading-bot
```

### 5. Stop the Bot

```bash
docker-compose down
```

## VPN Requirements

**Important**: If Alpaca API access is geographically restricted in your region, ensure your **VPN is enabled BEFORE starting the container**.

### Startup Behavior with VPN

1. **VPN Enabled**: Cache initializes normally (30-45 seconds), bot starts trading
2. **VPN Disabled**: Cache initialization times out after 45 seconds, bot starts with live data (slightly delayed indicator warm-up)
3. **VPN Disabled → Enabled During Boot**: Bot will start and warm up indicators with live data once VPN connection is established

The 45-second timeout prevents the container from hanging indefinitely if Alpaca is unreachable. No need to restart if you enable VPN after boot—the bot will seamlessly continue.

## Configuration

### Environment Variables

The Docker setup uses `.env` file for configuration. Environment variables have precedence over `config/config.yml`.

Key environment variables:

```env
ALPACA_API_KEY=your_key              # Required
ALPACA_SECRET_KEY=your_secret        # Required
TRADING_ENV=paper                    # paper or live
LOG_LEVEL=INFO                       # DEBUG, INFO, WARNING, ERROR
```

See `.env.example` for all available options.

### Config File

The bot also supports `config/config.yml` for settings. The precedence is:

1. **Environment Variables** (highest priority)
2. **config/config.yml**
3. **Defaults**

Example:

```yaml
app:
  trading_environment: paper
  broker: alpaca
  log_level: INFO
  max_position_size: 0.1
```

## Volume Mounts

The docker-compose setup mounts:

- `./logs` → `/app/logs` (container logs directory)
- `../config` → `/app/config` (configuration files)

This allows you to:
- Access logs from your host machine
- Modify strategy configuration without rebuilding

## Running Multiple Strategies

Edit `config/strategies.yaml` in the mounted config directory to enable/disable strategies:

```yaml
strategies:
  - name: "eur_usd_rsi_atr"
    class: "EURUSDStrategy"
    enabled: true  # Enable this strategy
    symbols:
      - "EURUSD"
```

## Development Mode

For development, you can mount the entire source code:

Edit `docker-compose.yml`:

```yaml
volumes:
  - ./logs:/app/logs
  - ../config:/app/config
  - ../src:/app/src  # Add this line
```

Then:

```bash
docker-compose up
```

Changes to Python code require container restart:

```bash
docker-compose restart trading-bot
```

## Switching Between Paper and Live Trading

### Option 1: Edit .env

```bash
# Change this line
TRADING_ENV=paper

# To this
TRADING_ENV=live

# Update API keys to live credentials
ALPACA_API_KEY=your_live_key
ALPACA_SECRET_KEY=your_live_secret
```

Then restart:

```bash
docker-compose restart trading-bot
```

### Option 2: Edit config.yml

```yaml
app:
  trading_environment: live
```

**IMPORTANT**: When switching to live:
1. Update API credentials
2. Verify account has proper funding
3. Start with small position sizes
4. Monitor closely

## Health Checks

The container includes a health check that verifies:
- Log file exists and is being written to

Check health:

```bash
docker ps
# Look for "healthy" status
```

## Resource Limits

The container is configured with:
- **CPU Limit**: 1 core
- **Memory Limit**: 512MB
- **Memory Reservation**: 256MB

Modify in `docker-compose.yml` if needed:

```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 1G
```

## Troubleshooting

### Bot doesn't start

Check logs:
```bash
docker-compose logs -f trading-bot
```

Common issues:
- Missing API credentials in `.env`
- Invalid market hours
- Network connectivity

### Configuration not loading

Verify `config/config.yml` exists and is valid YAML:

```bash
docker-compose exec trading-bot python -c "
import yaml
with open('config/config.yml') as f:
    yaml.safe_load(f)
print('YAML is valid')
"
```

### Logs not visible

Ensure `logs` directory exists:

```bash
mkdir -p logs
```

### High memory usage

Reduce resource limits or:
1. Reduce number of active strategies
2. Reduce data history window
3. Increase update interval

## Persistence

To persist logs and configuration changes:

1. **Logs** are saved to `./logs` (mounted volume)
2. **Config changes** to `../config` are persisted
3. **Trade history** can be stored (optional database setup)

## Production Deployment

For production:

1. Use secrets management instead of `.env`
   ```bash
   docker-compose up --env-file /path/to/secure/.env
   ```

2. Add restart policy:
   ```yaml
   restart_policy:
     condition: on-failure
     delay: 5s
     max_attempts: 5
   ```

3. Add monitoring:
   ```bash
   docker stats trading-bot
   ```

4. Use external logs:
   ```bash
   docker-compose logs > logs/external_logs.txt
   ```

## Docker Networking

The bot uses a custom network `trading-network` for:
- Future multi-service setups
- Database connections
- Monitoring services

To connect additional services:

```yaml
services:
  postgres:
    networks:
      - trading-network

networks:
  trading-network:
    driver: bridge
```

## Updating

To update the bot code:

```bash
# Pull latest changes
git pull

# Rebuild image
docker-compose build

# Run updated version
docker-compose up -d
```

## Cleanup

Remove unused images and volumes:

```bash
# Remove stopped containers
docker-compose rm

# Remove unused images
docker image prune

# Remove unused volumes
docker volume prune
```

## Support

For issues:
1. Check logs: `docker-compose logs -f`
2. Verify configuration files
3. Check Alpaca API status
4. Ensure network connectivity
