#!/bin/bash
# Docker entrypoint script for trading bot

set -e

echo "🤖 Trading Bot Startup"
echo "===================="

# Initialize database with Alembic migrations
echo "🗄️  Initializing database migrations..."
alembic upgrade head

# Initialize strategy cache if it doesn't exist
echo "⬇️  Checking strategy data cache..."
if [ ! -d "/app/data/cache" ] || [ -z "$(ls -A /app/data/cache)" ]; then
    echo "📥 Cache not found, downloading initial data from Alpaca..."
    python -m trading_bot.utils.data_cache refresh SPY QQQ
    echo "✅ Cache initialized successfully"
else
    echo "✅ Cache found, using existing data"
fi

# Start the bot
echo ""
echo "▶️  Starting trading bot..."
exec python -m trading_bot.main
