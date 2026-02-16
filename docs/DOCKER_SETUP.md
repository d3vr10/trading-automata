# Docker Setup Guide

Run the entire trading bot stack (bot + PostgreSQL database) with Docker Compose.

## Overview

The Docker setup includes:
- **trading-bot** - Trading bot application
- **postgres** - PostgreSQL 15 database
- **trading-network** - Internal network for communication
- **postgres_data** - Persistent volume for database

## Prerequisites

- Docker installed ([download](https://www.docker.com/products/docker-desktop))
- Docker Compose (included with Docker Desktop)
- Trading bot source code

## Quick Start (5 minutes)

### 1. Prepare Configuration

```bash
# Copy example configuration
cp .env.example .env

# Edit .env with your credentials
nano .env
```

**Minimum required in .env:**
```env
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
BROKER=alpaca
TRADING_ENV=paper
```

### 2. Start Services

```bash
# Build and start all containers
docker-compose -f docker/docker-compose.yml up -d

# View logs
docker-compose -f docker/docker-compose.yml logs -f trading-bot

# Check status
docker-compose -f docker/docker-compose.yml ps
```

### 3. Verify Services

```bash
# Check PostgreSQL is running
docker exec trading-bot-db psql -U postgres -d trading_bot -c "SELECT 1"

# Check bot is running
docker logs trading-bot | grep "Trading Bot initialized"
```

### 4. Stop Services

```bash
# Stop containers
docker-compose -f docker/docker-compose.yml down

# Stop and remove volumes (⚠️ deletes database!)
docker-compose -f docker/docker-compose.yml down -v
```

## Configuration

### Environment Variables

See `.env.example` for all available options.

**Required:**
```env
ALPACA_API_KEY=<your_key>
ALPACA_SECRET_KEY=<your_secret>
BROKER=alpaca
TRADING_ENV=paper
```

**Recommended:**
```env
LOG_LEVEL=INFO
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/trading_bot
```

**Optional:**
```env
TELEGRAM_TOKEN=<your_token>
TELEGRAM_CHAT_ID=<your_chat_id>
```

### Docker-Specific Configuration

When running in Docker, use these special settings:

```env
# Inside Docker container, use service name 'postgres' instead of 'localhost'
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/trading_bot
```

The `depends_on` clause ensures PostgreSQL is ready before trading bot starts.

## File Structure

```
trading-bot/
├── docker/
│   ├── docker-compose.yml      ← Main orchestration file
│   ├── Dockerfile              ← Bot image definition
│   └── .env.example            ← Environment template
├── .env                        ← Your configuration (git-ignored)
└── ...
```

## Services

### PostgreSQL (postgres)

```yaml
Service: postgres
Image: postgres:15-alpine
Container Name: trading-bot-db
Port: 5432 (exposed on localhost:5432)
Volume: postgres_data (persistent storage)
Health Check: pg_isready
Restart: unless-stopped
```

**Access PostgreSQL:**

```bash
# From inside Docker network
docker exec trading-bot-db psql -U postgres -d trading_bot

# From your machine
psql postgresql://postgres:postgres@localhost:5432/trading_bot

# Or with environment variables
PGPASSWORD=postgres psql -h localhost -U postgres -d trading_bot
```

### Trading Bot (trading-bot)

```yaml
Service: trading-bot
Image: Builds from docker/Dockerfile
Container Name: trading-bot
Depends On: postgres (service_healthy)
Environment: All settings from .env
Volumes: logs, config (mounted)
Restart: unless-stopped
Resources: 1 CPU, 512MB memory
```

## Common Tasks

### View Logs

```bash
# Recent logs
docker-compose -f docker/docker-compose.yml logs trading-bot

# Follow in real-time
docker-compose -f docker/docker-compose.yml logs -f trading-bot

# Last 100 lines
docker-compose -f docker/docker-compose.yml logs --tail=100 trading-bot
```

### Access Database

```bash
# Interactive psql session
docker exec -it trading-bot-db psql -U postgres -d trading_bot

# Run SQL directly
docker exec trading-bot-db psql -U postgres -d trading_bot -c "SELECT COUNT(*) FROM trades"

# Export data
docker exec trading-bot-db pg_dump -U postgres -d trading_bot > backup.sql
```

### Update Configuration

```bash
# Edit .env
nano .env

# Restart to apply changes
docker-compose -f docker/docker-compose.yml restart trading-bot
```

### Check Container Status

```bash
# List all containers
docker-compose -f docker/docker-compose.yml ps

# View container details
docker inspect trading-bot

# View resource usage
docker stats trading-bot trading-bot-db
```

### Rebuild Images

```bash
# Rebuild bot image (if you changed source code)
docker-compose -f docker/docker-compose.yml build trading-bot

# Rebuild and restart
docker-compose -f docker/docker-compose.yml up -d --build
```

## Troubleshooting

### "PostgreSQL connection refused"

**Problem:** Bot can't connect to database

**Solution:**
```bash
# Check PostgreSQL is running
docker-compose -f docker/docker-compose.yml ps

# Check database is healthy
docker exec trading-bot-db pg_isready -U postgres -d trading_bot

# View PostgreSQL logs
docker logs trading-bot-db
```

### "Cannot find container trading-bot-db"

**Problem:** Database container doesn't exist

**Solution:**
```bash
# Start containers
docker-compose -f docker/docker-compose.yml up -d

# Wait a few seconds, then check
docker-compose -f docker/docker-compose.yml ps
```

### "Database 'trading_bot' does not exist"

**Problem:** Schema not initialized

**Solution:**
```bash
# Initialize database schema
docker exec trading-bot python -m src.database.init

# Verify tables
docker exec trading-bot-db psql -U postgres -d trading_bot -c "\dt"
```

### "Trading bot won't start"

**Problem:** Container exits immediately

**Solution:**
```bash
# View logs
docker logs trading-bot

# Check configuration
docker exec trading-bot env | grep -i database

# Restart with logs visible
docker-compose -f docker/docker-compose.yml restart trading-bot
docker-compose -f docker/docker-compose.yml logs -f trading-bot
```

### "Permission denied" on volumes

**Problem:** Can't write to mounted volumes

**Solution:**
```bash
# Create directories if they don't exist
mkdir -p logs config

# Fix permissions
chmod 755 logs config

# Restart
docker-compose -f docker/docker-compose.yml restart
```

### Out of Disk Space

**Problem:** PostgreSQL volume is full

**Solution:**
```bash
# Check volume usage
docker volume inspect trading-bot_postgres_data

# Archive old trades (see DATABASE_SETUP.md)
docker exec trading-bot-db psql -U postgres -d trading_bot -c \
  "CREATE TABLE trades_archive AS SELECT * FROM trades WHERE entry_timestamp < NOW() - INTERVAL '6 months';"

# Or delete volume (⚠️ loses all data!)
docker-compose -f docker/docker-compose.yml down -v
docker-compose -f docker/docker-compose.yml up -d
```

## Production Considerations

### Security

**Don't use default credentials in production:**

```env
# ❌ Bad (default)
POSTGRES_PASSWORD=postgres

# ✅ Good (strong password)
POSTGRES_PASSWORD=$(openssl rand -base64 32)
```

**Expose PostgreSQL only internally:**

```yaml
# In docker-compose.yml, remove or comment out:
# ports:
#   - "5432:5432"

# This keeps database only accessible from other containers
```

**Use environment file instead of .env in production:**

```bash
# Create secure .env file
cp .env.example /etc/trading-bot/.env
chmod 600 /etc/trading-bot/.env

# Run with specific env file
docker-compose --env-file /etc/trading-bot/.env up -d
```

### Backups

**Daily database backups:**

```bash
#!/bin/bash
# backup_db.sh

BACKUP_DIR="backups/$(date +%Y-%m-%d)"
mkdir -p $BACKUP_DIR

docker exec trading-bot-db pg_dump -U postgres -d trading_bot | \
  gzip > $BACKUP_DIR/trading_bot_$(date +%H%M%S).sql.gz

# Keep only last 7 days
find backups -type d -mtime +7 -exec rm -rf {} \;
```

**Restore from backup:**

```bash
gunzip -c backups/2026-02-15/trading_bot_120000.sql.gz | \
  docker exec -i trading-bot-db psql -U postgres -d trading_bot
```

### Monitoring

**View resource usage:**

```bash
# Continuous monitoring
docker stats --no-stream

# CPU/Memory alerts
docker stats | awk '{if ($7 > "80%") print "HIGH MEMORY: " $1}'
```

**Check service health:**

```bash
# See health check status
docker ps --no-trunc | grep trading-bot

# View health check output
docker inspect --format='{{json .State.Health}}' trading-bot-db | jq .
```

## Advanced

### Custom Dockerfile

Edit `docker/Dockerfile` to:
- Change base image
- Install additional packages
- Add custom setup steps

### Multiple Environments

```bash
# Development
docker-compose -f docker/docker-compose.yml up -d

# Production (separate .env.prod)
docker-compose -f docker/docker-compose.prod.yml \
  --env-file .env.prod up -d
```

### Docker Network

Connect to bot from other containers:

```bash
docker network connect trading-network my-other-container
```

Access bot from other container:
```bash
# Host: trading-bot
# Port: 8000 (if you expose it)
```

## Reference

| Command | Purpose |
|---------|---------|
| `docker-compose up -d` | Start all services in background |
| `docker-compose down` | Stop all services |
| `docker-compose logs -f` | Follow logs |
| `docker-compose ps` | Show status |
| `docker-compose restart` | Restart services |
| `docker-compose exec <service> <cmd>` | Run command in container |

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string |
| `POSTGRES_USER` | Database user (default: postgres) |
| `POSTGRES_PASSWORD` | Database password (default: postgres) |
| `POSTGRES_DB` | Database name (default: trading_bot) |

## Related Documentation

- **Broker Setup:** `MULTI_BROKER_SETUP.md`
- **Database:** `DATABASE_SETUP.md`
- **Telegram:** `TELEGRAM_SETUP.md`
- **Alembic Migrations:** `ALEMBIC_MIGRATIONS.md`

---

**Ready to go!** Run `docker-compose -f docker/docker-compose.yml up -d` and your trading bot is live. 🚀