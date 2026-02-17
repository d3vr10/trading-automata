"""Strategy warm-up utility to pre-load historical data.

This script pulls historical bars from Alpaca and pre-populates strategy
price history so indicators are calculated immediately on bot startup.

Usage:
    from trading_bot.utils.strategy_warmer import warm_up_strategy
    warm_up_strategy(strategy, symbol, bars=50)
"""

import logging
from typing import Optional, List
from trading_bot.data.models import Bar

logger = logging.getLogger(__name__)


def fetch_historical_bars(symbol: str, num_bars: int = 100, use_cache: bool = True) -> List[Bar]:
    """Fetch historical bars from cache or Alpaca API.

    Args:
        symbol: Stock symbol (e.g., 'SPY', 'QQQ')
        num_bars: Number of historical bars to fetch (default 100)
        use_cache: Use cached data if available (default True)

    Returns:
        List of Bar objects with OHLCV data
    """
    try:
        from trading_bot.utils.data_cache import get_bars
        return get_bars(symbol, use_cache=use_cache, num_bars=num_bars)

    except Exception as e:
        logger.error(f"Failed to fetch historical bars for {symbol}: {e}")
        return []


def warm_up_strategy(strategy, symbol: str, num_bars: int = 100, use_cache: bool = True) -> bool:
    """Pre-load historical data into a strategy.

    Feeds historical bars through the strategy's on_bar() method to properly
    initialize internal indicators and state without generating recorded signals.

    Args:
        strategy: BaseStrategy instance
        symbol: Stock symbol to warm up
        num_bars: Number of historical bars to load (default 100)
        use_cache: Use cached data if available (default True)

    Returns:
        True if warm-up successful, False otherwise
    """
    logger.info(f"Warming up strategy {strategy.name} for {symbol}...")

    # Fetch historical data (from cache or API)
    bars = fetch_historical_bars(symbol, num_bars, use_cache=use_cache)

    if not bars:
        logger.error(f"Could not fetch historical data for {symbol}")
        return False

    logger.info(f"Fetched {len(bars)} historical bars for {symbol}")

    # Feed bars into strategy to initialize internal state
    # This calls on_bar() for each bar, which initializes indicators and state,
    # but we don't record or act on the signals during warm-up
    signal_count = 0
    for i, bar in enumerate(bars):
        try:
            # Call on_bar() to process the bar and populate strategy's internal state
            # This initializes the strategy's indicators without recording signals
            signal = strategy.on_bar(bar)
            if signal:
                signal_count += 1
                logger.debug(f"  Bar {i+1}/{len(bars)}: Signal generated (not executed): {signal}")
        except Exception as e:
            logger.error(f"Error during warm-up for {symbol}: {e}")
            return False

    logger.info(
        f"Strategy {strategy.name} warmed up: {len(bars)} bars processed, "
        f"{signal_count} signals generated (discarded). Ready to trade {symbol}!"
    )

    return True


def warm_up_all_strategies(strategies: List, symbols: Optional[List[str]] = None,
                          num_bars: int = 100, use_cache: bool = True) -> int:
    """Warm up all strategies with historical data.

    Args:
        strategies: List of BaseStrategy instances
        symbols: Symbols to warm up (if None, uses all strategy symbols)
        num_bars: Number of historical bars per symbol
        use_cache: Use cached data if available (default True)

    Returns:
        Number of strategies successfully warmed up
    """
    logger.info(f"Warming up {len(strategies)} strategies (use_cache={use_cache})...")

    successful = 0

    for strategy in strategies:
        # Get symbols for this strategy
        strategy_symbols = symbols or strategy.config.get('symbols', [])

        for symbol in strategy_symbols:
            if warm_up_strategy(strategy, symbol, num_bars, use_cache=use_cache):
                successful += 1
            else:
                logger.warning(f"Failed to warm up {strategy.name} for {symbol}")

    logger.info(f"Warm-up complete: {successful} strategy/symbol combinations ready")
    return successful
