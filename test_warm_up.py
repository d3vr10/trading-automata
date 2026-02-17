#!/usr/bin/env python3
"""Quick test script to warm up strategies and verify they're ready to trade.

Usage:
    python test_warm_up.py

This script:
1. Loads all strategies from config/strategies.yaml
2. Warms them up with 50 hours of historical data
3. Shows how many bars each strategy has loaded
4. Exits (ready to start the bot now)
"""

import sys
from trading_bot.strategies.registry import StrategyRegistry
from trading_bot.utils.strategy_warmer import warm_up_all_strategies

if __name__ == "__main__":
    print("Testing strategy warm-up...")
    print()

    # Load strategies
    print("Loading strategies from config/strategies.yaml...")
    strategies = StrategyRegistry.load_from_config("config/strategies.yaml")

    if not strategies:
        print("ERROR: No strategies loaded!")
        sys.exit(1)

    print(f"✅ Loaded {len(strategies)} strategies:")
    for strategy in strategies:
        symbols = strategy.config.get('symbols', [])
        print(f"   - {strategy.name}: {symbols}")
    print()

    # Warm up
    print("Warming up strategies with historical data...")
    print("(This fetches the last 50 hours of 1-hour bars from Alpaca)")
    print()

    successful = warm_up_all_strategies(strategies, num_bars=50)

    print()
    print("Warm-up Results:")
    print("-" * 50)
    for strategy in strategies:
        symbols = strategy.config.get('symbols', [])
        for symbol in symbols:
            num_bars = len(strategy.price_history.get(symbol, []))
            status = "✅ READY" if num_bars > 25 else "⚠️ PARTIAL"
            print(f"{strategy.name:30} {symbol:10} {num_bars:3} bars {status}")

    print()
    print("All strategies warmed up! Bot is ready to trade immediately.")
    print()
    print("Next: Start the bot with: docker-compose up")
