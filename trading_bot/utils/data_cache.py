"""Data caching system for deterministic strategy testing.

Allows downloading real Alpaca data and caching it locally for
reproducible testing while maintaining production alignment.

Usage:
    # Download and cache data from Alpaca
    python -m trading_bot.utils.data_cache refresh SPY QQQ

    # Clear cache
    python -m trading_bot.utils.data_cache clear SPY
"""

import logging
import csv
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timedelta
from decimal import Decimal

from alpaca.data.requests import StockBarsRequest
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.timeframe import TimeFrame
from trading_bot.data.models import Bar

logger = logging.getLogger(__name__)

# Cache directory
CACHE_DIR = Path("data/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_cache_path(symbol: str) -> Path:
    """Get cache file path for a symbol."""
    return CACHE_DIR / f"{symbol.lower()}_bars.csv"


def save_bars_to_cache(symbol: str, bars: List[Bar]) -> bool:
    """Save bars to CSV cache file.

    Args:
        symbol: Stock symbol
        bars: List of Bar objects

    Returns:
        True if successful
    """
    try:
        cache_file = get_cache_path(symbol)

        with open(cache_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'open', 'high', 'low', 'close', 'volume'])

            for bar in bars:
                writer.writerow([
                    bar.timestamp.isoformat(),
                    str(bar.open),
                    str(bar.high),
                    str(bar.low),
                    str(bar.close),
                    str(bar.volume)
                ])

        logger.info(f"Cached {len(bars)} bars for {symbol} to {cache_file}")
        return True

    except Exception as e:
        logger.error(f"Failed to cache data for {symbol}: {e}")
        return False


def load_bars_from_cache(symbol: str, num_bars: int = 100) -> List[Bar]:
    """Load bars from CSV cache file.

    Args:
        symbol: Stock symbol
        num_bars: Number of bars to return (returns last N bars from cache)

    Returns:
        List of Bar objects, or empty list if cache doesn't exist
    """
    try:
        cache_file = get_cache_path(symbol)

        if not cache_file.exists():
            logger.debug(f"No cache found for {symbol} at {cache_file}")
            return []

        bars = []
        with open(cache_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                bar = Bar(
                    symbol=symbol,
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    open=Decimal(row['open']),
                    high=Decimal(row['high']),
                    low=Decimal(row['low']),
                    close=Decimal(row['close']),
                    volume=int(row['volume'])
                )
                bars.append(bar)

        # Return last num_bars
        result = bars[-num_bars:] if len(bars) > num_bars else bars
        logger.info(f"Loaded {len(result)} bars for {symbol} from cache")
        return result

    except Exception as e:
        logger.error(f"Failed to load cache for {symbol}: {e}")
        return []


def fetch_and_cache_bars(symbol: str, num_bars: int = 100) -> List[Bar]:
    """Fetch bars from Alpaca API and save to cache.

    Args:
        symbol: Stock symbol
        num_bars: Number of historical bars to fetch

    Returns:
        List of Bar objects
    """
    try:
        logger.info(f"Fetching {num_bars} bars for {symbol} from Alpaca...")

        # Get credentials from settings
        from config.settings import load_settings
        settings = load_settings()
        client = StockHistoricalDataClient(
            settings.alpaca_api_key,
            settings.alpaca_secret_key
        )

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=num_bars + 10)

        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.HOUR,
            start=start_date,
            end=end_date,
        )

        bars_data = client.get_stock_bars(request)

        if symbol not in bars_data.df.index.get_level_values(0):
            logger.warning(f"No data found for {symbol}")
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

        # Sort and return last num_bars
        bars.sort(key=lambda b: b.timestamp)
        result = bars[-num_bars:] if len(bars) > num_bars else bars

        # Save to cache
        save_bars_to_cache(symbol, result)

        return result

    except (ConnectionError, TimeoutError) as e:
        logger.error(f"Connection error fetching {symbol} from Alpaca: {e}")
        logger.error("⚠️  Alpaca unreachable - check VPN connection, network, and API credentials")
        return []
    except Exception as e:
        logger.error(f"Failed to fetch bars for {symbol}: {e}")
        return []


def get_bars(symbol: str, use_cache: bool = True, num_bars: int = 100) -> List[Bar]:
    """Get bars, preferring cache if available and enabled.

    Args:
        symbol: Stock symbol
        use_cache: If True, try cache first; if False, always fetch from API
        num_bars: Number of bars to return

    Returns:
        List of Bar objects
    """
    # Try cache first if enabled
    if use_cache:
        cached_bars = load_bars_from_cache(symbol, num_bars)
        if cached_bars:
            return cached_bars
        logger.debug(f"Cache miss for {symbol}, fetching from API...")

    # Fall back to API
    return fetch_and_cache_bars(symbol, num_bars)


def clear_cache(symbol: Optional[str] = None) -> bool:
    """Clear cache for a symbol or all symbols.

    Args:
        symbol: Symbol to clear (if None, clear all)

    Returns:
        True if successful
    """
    try:
        if symbol:
            cache_file = get_cache_path(symbol)
            if cache_file.exists():
                cache_file.unlink()
                logger.info(f"Cleared cache for {symbol}")
            return True
        else:
            # Clear all
            import shutil
            if CACHE_DIR.exists():
                shutil.rmtree(CACHE_DIR)
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                logger.info("Cleared all cached data")
            return True

    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        return False


if __name__ == "__main__":
    import sys

    # CLI for cache management
    if len(sys.argv) < 2:
        print("Usage: python -m trading_bot.utils.data_cache [refresh|clear] [symbol1] [symbol2]...")
        sys.exit(1)

    command = sys.argv[1]
    symbols = sys.argv[2:] if len(sys.argv) > 2 else ["SPY", "QQQ"]

    if command == "refresh":
        print(f"Refreshing cache for {symbols}...")
        for symbol in symbols:
            fetch_and_cache_bars(symbol, num_bars=100)
        print("✅ Cache updated!")

    elif command == "clear":
        for symbol in symbols:
            clear_cache(symbol)
        print("✅ Cache cleared!")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
