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
    echo "📥 Cache not found, attempting to download from Alpaca..."
    echo "⏱️  (timeout: 45 seconds - if VPN is required, ensure it's enabled)"

    # Use timeout command to prevent indefinite hangs if Alpaca is unreachable
    # Continue with bot startup even if cache download fails - it will use live data
    if timeout 45 python -m trading_automata.utils.data_cache refresh SPY QQQ 2>/dev/null; then
        echo "✅ Cache initialized successfully"
    else
        cache_result=$?
        if [ $cache_result -eq 124 ]; then
            echo "⚠️  Cache download timed out (Alpaca unreachable - ensure VPN is enabled)"
        else
            echo "⚠️  Cache download failed - bot will use live data"
        fi
        echo "   Bot startup will proceed - strategies will warm-up with live market data"
    fi
else
    echo "✅ Cache found, using existing data"
fi

# Start the bot
echo ""
echo "▶️  Starting trading bot..."
exec python -m trading_automata.main
