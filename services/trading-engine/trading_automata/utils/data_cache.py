"""Data caching system for deterministic strategy testing.

Allows downloading real Alpaca data and caching it locally for
reproducible testing while maintaining production alignment.

Usage:
    # Download and cache data from Alpaca
    python -m trading_automata.utils.data_cache refresh SPY QQQ

    # Clear cache
    python -m trading_automata.utils.data_cache clear SPY
"""

import logging
import csv
import math
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timedelta
from decimal import Decimal

import pandas as pd
from alpaca.data.requests import StockBarsRequest
from alpaca.data.historical import StockHistoricalDataClient
from trading_automata.data.models import Bar
from trading_automata.data.alpaca_data import AlpacaDataProvider

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

    Falls back to yfinance if Alpaca is unavailable (e.g., SIP restrictions,
    network issues). This ensures cache can always be populated during Docker startup.

    Args:
        symbol: Stock symbol
        num_bars: Number of historical bars to fetch

    Returns:
        List of Bar objects
    """
    # Try Alpaca first
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

        # Use the timeframe parser from AlpacaDataProvider to get correct enum
        timeframe = AlpacaDataProvider._parse_timeframe("1h")
        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=timeframe,
            start=start_date,
            end=end_date,
        )

        bars_data = client.get_stock_bars(request)

        if symbol not in bars_data.df.index.get_level_values(0):
            logger.warning(f"No data found for {symbol} on Alpaca")
            raise ValueError(f"No data for {symbol}")

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
        logger.info(f"✅ Fetched {len(result)} bars from Alpaca for {symbol}")

        return result

    except Exception as alpaca_error:
        logger.warning(f"Alpaca fetch failed for {symbol}: {alpaca_error}")
        logger.info(f"Falling back to yfinance for {symbol}...")
        return _fetch_from_yfinance(symbol, num_bars)


def _fetch_from_yfinance(symbol: str, num_bars: int = 100) -> List[Bar]:
    """Fetch historical bars from Yahoo Finance as fallback.

    Used when Alpaca is unavailable (SIP restrictions, network issues, etc.)
    This provides free, unrestricted access to historical data for testing.

    Args:
        symbol: Stock symbol
        num_bars: Number of historical bars to fetch

    Returns:
        List of Bar objects
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance not installed. Install with: pip install yfinance")
        return []

    try:
        # Crypto symbols need -USD suffix for Yahoo Finance (e.g., BTC -> BTC-USD)
        CRYPTO_SYMBOLS = {
            "BTC", "ETH", "SOL", "DOGE", "ADA", "XRP", "AVAX", "DOT", "MATIC",
            "LINK", "UNI", "ATOM", "LTC", "BCH", "NEAR", "APT", "ARB", "OP",
            "FIL", "AAVE", "MKR", "CRV", "SHIB", "PEPE", "SUI", "SEI",
        }
        yf_symbol = f"{symbol}-USD" if symbol.upper() in CRYPTO_SYMBOLS and "-" not in symbol else symbol
        logger.info(f"Fetching {num_bars} bars for {symbol} from Yahoo Finance (ticker: {yf_symbol})...")

        logger.info(f"Downloading 1 year of daily bars for {yf_symbol}...")
        logger.debug(f"yfinance version: {yf.__version__ if hasattr(yf, '__version__') else 'unknown'}")

        data = yf.download(
            yf_symbol,
            period="1y",
            interval="1d",  # Daily bars instead of hourly (more reliable)
            progress=False,
            threads=False  # Disable threading to avoid issues
        )

        logger.debug(f"Download completed. Data type: {type(data)}")

        if data is None:
            logger.error(f"yfinance returned None for {symbol}")
            return []

        if data.empty:
            logger.warning(f"yfinance returned empty dataframe for {symbol}")
            return []

        logger.debug(f"Data shape: {data.shape}")
        logger.debug(f"Data columns: {data.columns.tolist()}")
        logger.debug(f"Data index type: {type(data.index)}")
        logger.debug(f"First row:\n{data.head(1)}")

        # Ensure data has the expected columns
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        missing_cols = [col for col in required_cols if col not in data.columns]
        if missing_cols:
            logger.error(f"Data for {symbol} missing columns: {missing_cols}. Got: {data.columns.tolist()}")
            return []

        # Remove rows with any NaN values
        initial_len = len(data)
        data = data.dropna()
        dropped = initial_len - len(data)
        logger.info(f"Cleaned data: {initial_len} rows → {len(data)} rows (dropped {dropped} NaN rows)")

        if len(data) == 0:
            logger.error(f"No valid data remaining for {symbol} after removing NaN values")
            return []

        # Convert to Bar objects
        bars = []
        conversion_errors = []

        # Handle MultiIndex columns from yfinance (columns are tuples like ('Open', 'SPY'))
        has_multiindex = isinstance(data.columns, pd.MultiIndex)
        logger.debug(f"MultiIndex columns: {has_multiindex}")
        logger.debug(f"Data columns: {list(data.columns)}")
        logger.debug(f"First few rows:\n{data.head(3)}")

        for idx, (timestamp, row) in enumerate(data.iterrows()):
            try:
                logger.debug(f"Row {idx}: timestamp={timestamp}, row_type={type(row)}, row_values={dict(row)}")

                # Access columns - handle both regular and MultiIndex columns
                if has_multiindex:
                    logger.debug(f"Using MultiIndex access for row {idx}")
                    open_val = float(row[('Open', symbol)])
                    high_val = float(row[('High', symbol)])
                    low_val = float(row[('Low', symbol)])
                    close_val = float(row[('Close', symbol)])
                    volume_val = int(float(row[('Volume', symbol)]))  # Convert via float for safety
                else:
                    logger.debug(f"Using regular column access for row {idx}")
                    open_val = float(row['Open'])
                    high_val = float(row['High'])
                    low_val = float(row['Low'])
                    close_val = float(row['Close'])
                    volume_val = int(float(row['Volume']))  # Convert via float for safety

                logger.debug(f"Row {idx} converted: O={open_val}, H={high_val}, L={low_val}, C={close_val}, V={volume_val}")

                # Validate data before Bar creation
                if high_val < low_val:
                    logger.warning(f"Row {idx}: High ({high_val}) < Low ({low_val}) - invalid OHLC")
                if any(v < 0 for v in [open_val, high_val, low_val, close_val]):
                    logger.warning(f"Row {idx}: Negative price detected - O={open_val}, H={high_val}, L={low_val}, C={close_val}")

                bar = Bar(
                    symbol=symbol,
                    timestamp=timestamp.to_pydatetime() if hasattr(timestamp, 'to_pydatetime') else timestamp,
                    open=Decimal(str(open_val)),
                    high=Decimal(str(high_val)),
                    low=Decimal(str(low_val)),
                    close=Decimal(str(close_val)),
                    volume=volume_val
                )
                bars.append(bar)
            except ValueError as ve:
                # Catch validation errors from Bar.__post_init__
                import traceback
                error_msg = f"Row {idx}: Validation error: {ve}"
                logger.warning(f"Failed to convert row {idx} for {symbol}: {error_msg}")
                logger.debug(f"Row {idx} traceback: {traceback.format_exc()}")
                conversion_errors.append(error_msg)
                continue
            except Exception as e:
                import traceback
                error_msg = f"Row {idx}: {type(e).__name__}: {e}"
                logger.warning(f"Failed to convert row {idx} for {symbol}: {error_msg}")
                logger.debug(f"Row {idx} traceback: {traceback.format_exc()}")
                conversion_errors.append(error_msg)
                continue

        logger.info(f"Converted {len(bars)}/{len(data)} rows for {symbol} ({100*len(bars)//len(data)}%)")

        if conversion_errors:
            logger.warning(f"⚠️  {len(conversion_errors)} rows failed to convert for {symbol}")
            # Log first 3 errors as examples
            for error in conversion_errors[:3]:
                logger.warning(f"  Example failure: {error}")
            if len(conversion_errors) > 3:
                logger.warning(f"  ... and {len(conversion_errors) - 3} more errors")

        # Sort and return last num_bars
        bars.sort(key=lambda b: b.timestamp)
        result = bars[-num_bars:] if len(bars) > num_bars else bars

        logger.info(f"Returning {len(result)} bars for {symbol}")

        # Save to cache
        save_bars_to_cache(symbol, result)
        logger.info(f"✅ Fetched {len(result)} daily bars from Yahoo Finance for {symbol}")

        return result

    except Exception as e:
        import traceback
        logger.error(f"Failed to fetch bars from Yahoo Finance for {symbol}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Exception message: {str(e)}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
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
        print("Usage: python -m trading_automata.utils.data_cache [refresh|clear] [symbol1] [symbol2]...")
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
