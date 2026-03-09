#!/bin/bash
# Docker entrypoint script for trading engine service

set -e

echo "Trading Automata - Engine Service"
echo "================================="

# Initialize database with Alembic migrations
echo "Initializing database migrations..."
alembic upgrade head

# Initialize strategy cache if it doesn't exist
echo "Checking strategy data cache..."
if [ ! -d "/app/data/cache" ] || [ -z "$(ls -A /app/data/cache 2>/dev/null)" ]; then
    echo "Cache not found, attempting to download from Alpaca..."
    echo "(timeout: 45 seconds - if VPN is required, ensure it's enabled)"

    if timeout 45 python -m trading_automata.utils.data_cache refresh SPY QQQ 2>/dev/null; then
        echo "Cache initialized successfully"
    else
        cache_result=$?
        if [ $cache_result -eq 124 ]; then
            echo "WARNING: Cache download timed out (Alpaca unreachable)"
        else
            echo "WARNING: Cache download failed - bot will use live data"
        fi
        echo "Bot startup will proceed - strategies will warm-up with live market data"
    fi
else
    echo "Cache found, using existing data"
fi

# Start the trading engine
echo ""
echo "Starting trading engine..."
exec python -m trading_automata.main
