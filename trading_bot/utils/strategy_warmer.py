"""Strategy warm-up utility to pre-load historical data.

This script pulls historical bars from Alpaca and pre-populates strategy
price history so indicators are calculated immediately on bot startup.

Usage:
    from trading_bot.utils.strategy_warmer import warm_up_strategy
    warm_up_strategy(strategy, symbol, bars=50)
"""

import logging
from typing import Optional, List
from datetime import datetime, timedelta
from decimal import Decimal
from alpaca.data.requests import StockBarsRequest
from alpaca.data.client import StockHistoricalDataClient
from trading_bot.data.models import Bar

logger = logging.getLogger(__name__)


def fetch_historical_bars(symbol: str, num_bars: int = 100) -> List[Bar]:
    """Fetch historical bars from Alpaca.

    Args:
        symbol: Stock symbol (e.g., 'SPY', 'QQQ')
        num_bars: Number of historical bars to fetch (default 100)

    Returns:
        List of Bar objects with OHLCV data
    """
    try:
        client = StockHistoricalDataClient()

        # Calculate date range (roughly 1 bar per day, so num_bars days back)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=num_bars + 10)  # Extra buffer

        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe="Hour",  # 1-hour bars
            start=start_date,
            end=end_date,
        )

        bars_data = client.get_stock_bars(request)

        if symbol not in bars_data.df.index.get_level_values(0):
            logger.warning(f"No historical data found for {symbol}")
            return []

        symbol_data = bars_data.df.loc[symbol]

        # Convert to Bar objects
        bars = []
        for idx, row in symbol_data.iterrows():
            bar = Bar(
                symbol=symbol,
                timestamp=idx if isinstance(idx, datetime) else datetime.fromisoformat(str(idx)),
                open=Decimal(str(row['open'])),
                high=Decimal(str(row['high'])),
                low=Decimal(str(row['low'])),
                close=Decimal(str(row['close'])),
                volume=int(row['volume'])
            )
            bars.append(bar)

        # Sort by timestamp ascending
        bars.sort(key=lambda b: b.timestamp)

        # Return last num_bars
        return bars[-num_bars:] if len(bars) > num_bars else bars

    except Exception as e:
        logger.error(f"Failed to fetch historical bars for {symbol}: {e}")
        return []


def warm_up_strategy(strategy, symbol: str, num_bars: int = 100) -> bool:
    """Pre-load historical data into a strategy.

    Args:
        strategy: BaseStrategy instance
        symbol: Stock symbol to warm up
        num_bars: Number of historical bars to load (default 100)

    Returns:
        True if warm-up successful, False otherwise
    """
    logger.info(f"Warming up strategy {strategy.name} for {symbol}...")

    # Fetch historical data
    bars = fetch_historical_bars(symbol, num_bars)

    if not bars:
        logger.error(f"Could not fetch historical data for {symbol}")
        return False

    logger.info(f"Fetched {len(bars)} historical bars for {symbol}")

    # Initialize symbol history if needed
    if symbol not in strategy.price_history:
        strategy.price_history[symbol] = []
        strategy.high_history[symbol] = []
        strategy.low_history[symbol] = []
        strategy.volume_history[symbol] = []

    # Feed bars into strategy (without generating signals)
    for bar in bars:
        strategy.price_history[symbol].append(float(bar.close))
        strategy.high_history[symbol].append(float(bar.high))
        strategy.low_history[symbol].append(float(bar.low))
        strategy.volume_history[symbol].append(int(bar.volume))

    logger.info(
        f"Strategy {strategy.name} warmed up with {len(bars)} bars. "
        f"Ready to trade {symbol}!"
    )

    return True


def warm_up_all_strategies(strategies: List, symbols: Optional[List[str]] = None,
                          num_bars: int = 100) -> int:
    """Warm up all strategies with historical data.

    Args:
        strategies: List of BaseStrategy instances
        symbols: Symbols to warm up (if None, uses all strategy symbols)
        num_bars: Number of historical bars per symbol

    Returns:
        Number of strategies successfully warmed up
    """
    logger.info(f"Warming up {len(strategies)} strategies...")

    successful = 0

    for strategy in strategies:
        # Get symbols for this strategy
        strategy_symbols = symbols or strategy.config.get('symbols', [])

        for symbol in strategy_symbols:
            if warm_up_strategy(strategy, symbol, num_bars):
                successful += 1
            else:
                logger.warning(f"Failed to warm up {strategy.name} for {symbol}")

    logger.info(f"Warm-up complete: {successful} strategy/symbol combinations ready")
    return successful
