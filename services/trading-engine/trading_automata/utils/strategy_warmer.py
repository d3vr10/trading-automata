"""Strategy warm-up utility to pre-load historical data.

Pulls historical bars and pre-populates strategy price history so indicators
are calculated immediately on bot startup.

Data source priority:
  1. Bot's own data_provider (already authenticated, works for any broker)
  2. Local CSV cache (from previous runs)
  3. Global Alpaca credentials (legacy, from config/settings.py)
  4. yfinance fallback (no API key needed, covers stocks + crypto)

Usage:
    from trading_automata.utils.strategy_warmer import warm_up_all_strategies
    warm_up_all_strategies(strategies, data_provider=bot.data_provider)
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List

from trading_automata.data.base import IDataProvider
from trading_automata.data.models import Bar

logger = logging.getLogger(__name__)


def _fetch_from_provider(
    data_provider: IDataProvider, symbol: str, num_bars: int
) -> List[Bar]:
    """Fetch historical bars using the bot's own data provider."""
    try:
        # Request extra days to account for weekends/holidays (equities)
        days = int(num_bars * 1.8) + 10
        end = datetime.now()
        start = end - timedelta(days=days)
        bars = data_provider.get_bars(symbol, "1d", start, end)
        if bars:
            bars.sort(key=lambda b: b.timestamp)
            return bars[-num_bars:] if len(bars) > num_bars else bars
    except Exception as e:
        logger.warning(f"Data provider fetch failed for {symbol}: {e}")
    return []


def fetch_historical_bars(
    symbol: str,
    num_bars: int = 100,
    use_cache: bool = True,
    data_provider: Optional[IDataProvider] = None,
) -> List[Bar]:
    """Fetch historical bars with fallback chain.

    Priority: data_provider → cache → global Alpaca → yfinance.

    Args:
        symbol: Stock/crypto symbol
        num_bars: Number of historical bars to fetch
        use_cache: Use cached data if available
        data_provider: Bot's connected data provider (preferred source)

    Returns:
        List of Bar objects with OHLCV data
    """
    # 1. Try bot's own data provider (already authenticated)
    if data_provider is not None:
        bars = _fetch_from_provider(data_provider, symbol, num_bars)
        if bars:
            logger.info(f"Fetched {len(bars)} bars for {symbol} from data provider")
            # Update cache for future cold starts
            try:
                from trading_automata.utils.data_cache import save_bars_to_cache
                save_bars_to_cache(symbol, bars)
            except Exception:
                pass
            return bars

    # 2. Fall back to cache / global credentials / yfinance
    try:
        from trading_automata.utils.data_cache import get_bars
        return get_bars(symbol, use_cache=use_cache, num_bars=num_bars)
    except Exception as e:
        logger.error(f"Failed to fetch historical bars for {symbol}: {e}")
        return []


def warm_up_strategy(
    strategy,
    symbol: str,
    num_bars: int = 100,
    use_cache: bool = True,
    data_provider: Optional[IDataProvider] = None,
) -> bool:
    """Pre-load historical data into a strategy.

    Feeds historical bars through the strategy's on_bar() method to properly
    initialize internal indicators and state without generating recorded signals.

    Args:
        strategy: BaseStrategy instance
        symbol: Stock symbol to warm up
        num_bars: Number of historical bars to load
        use_cache: Use cached data if available
        data_provider: Bot's connected data provider (preferred source)

    Returns:
        True if warm-up successful, False otherwise
    """
    logger.info(f"Warming up strategy {strategy.name} for {symbol}...")

    bars = fetch_historical_bars(symbol, num_bars, use_cache=use_cache,
                                 data_provider=data_provider)

    if not bars:
        logger.warning(f"No historical data for {symbol} — strategy starts cold")
        return False

    logger.info(f"Fetched {len(bars)} historical bars for {symbol}")

    signal_count = 0
    for i, bar in enumerate(bars):
        try:
            signal = strategy.on_bar(bar)
            if signal:
                signal_count += 1
        except Exception as e:
            logger.error(f"Error during warm-up for {symbol}: {e}")
            return False

    logger.info(
        f"Strategy {strategy.name} warmed up: {len(bars)} bars processed, "
        f"{signal_count} signals generated (discarded). Ready to trade {symbol}!"
    )
    return True


def warm_up_all_strategies(
    strategies: List,
    symbols: Optional[List[str]] = None,
    num_bars: int = 100,
    use_cache: bool = True,
    data_provider: Optional[IDataProvider] = None,
) -> int:
    """Warm up all strategies with historical data.

    Args:
        strategies: List of BaseStrategy instances
        symbols: Symbols to warm up (if None, uses each strategy's symbols)
        num_bars: Number of historical bars per symbol
        use_cache: Use cached data if available
        data_provider: Bot's connected data provider (preferred source)

    Returns:
        Number of strategy/symbol combinations successfully warmed up
    """
    logger.info(f"Warming up {len(strategies)} strategies...")

    successful = 0

    for strategy in strategies:
        strategy_symbols = symbols or strategy.config.get('symbols', [])

        for symbol in strategy_symbols:
            if warm_up_strategy(strategy, symbol, num_bars, use_cache=use_cache,
                                data_provider=data_provider):
                successful += 1
            else:
                logger.warning(f"Failed to warm up {strategy.name} for {symbol}")

    logger.info(f"Warm-up complete: {successful} strategy/symbol combinations ready")
    return successful
