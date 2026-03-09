#!/usr/bin/env python3
"""Quick test script to warm up strategies and verify they're ready to trade.

Usage:
    python test_warm_up.py           # Test with cached data
    python test_warm_up.py --live    # Test with fresh API data
    python test_warm_up.py --refresh # Download & cache fresh data first

This script:
1. Loads all strategies from config/strategies.yaml
2. Warms them up with 50 hours of historical data (cached or live)
3. Shows how many bars each strategy has loaded
4. Exits (ready to start the bot now)
"""

import sys
from trading_automata.strategies.registry import StrategyRegistry
from trading_automata.utils.strategy_warmer import warm_up_all_strategies

if __name__ == "__main__":
    use_cache = True

    # Parse command line arguments
    if "--live" in sys.argv:
        use_cache = False
        print("🔴 LIVE MODE: Fetching fresh data from Alpaca API...")
    elif "--refresh" in sys.argv:
        print("⬇️  REFRESHING CACHE: Downloading latest data from Alpaca...")
        from trading_automata.utils.data_cache import fetch_and_cache_bars
        for symbol in ["SPY", "QQQ"]:
            fetch_and_cache_bars(symbol, num_bars=100)
        print("✅ Cache refreshed!")
        print()
    else:
        print("🟢 CACHED MODE: Using local cached data (deterministic testing)...")

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
    if use_cache:
        print("(Loading from local cache - instant)")
    else:
        print("(Fetching fresh data from Alpaca API)")
    print()

    successful = warm_up_all_strategies(strategies, num_bars=50, use_cache=use_cache)

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
