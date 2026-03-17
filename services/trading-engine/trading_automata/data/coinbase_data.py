"""Coinbase data provider implementation.

Uses the Coinbase Advanced Trading REST API to fetch historical
candles and latest market data for crypto pairs.
"""

import logging
from typing import List, Optional, Callable
from datetime import datetime
from decimal import Decimal

from .base import IDataProvider
from .models import Bar, Quote, Trade

try:
    from coinbase.rest import RESTClient
except ImportError:
    RESTClient = None

logger = logging.getLogger(__name__)

# Coinbase candle granularities (in seconds)
_GRANULARITY_MAP = {
    "1min": "ONE_MINUTE",
    "5min": "FIVE_MINUTE",
    "15min": "FIFTEEN_MINUTE",
    "30min": "THIRTY_MINUTE",
    "1h": "ONE_HOUR",
    "6h": "SIX_HOUR",
    "1d": "ONE_DAY",
    "day": "ONE_DAY",
}


def _g(obj, key, default=None):
    """Safely get a value from a dict or SDK response object."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    try:
        val = obj[key]
        return val if val is not None else default
    except (KeyError, TypeError, IndexError):
        return default


def _parse_candles(response):
    """Extract candle list from SDK response (handles dict, list, or object)."""
    if isinstance(response, dict):
        return response.get("candles", [])
    if isinstance(response, list):
        return response
    if hasattr(response, "candles"):
        candles = response.candles
        return list(candles) if candles else []
    return []


class CoinbaseDataProvider(IDataProvider):
    """Coinbase data provider for crypto market data.

    Uses Coinbase Advanced Trading API for historical candles
    and latest market data. Supports crypto pairs only (e.g., BTC-USD).
    """

    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.client = None
        self._connected = False
        self._bar_callbacks = {}
        self._quote_callbacks = {}
        self._trade_callbacks = {}

    def connect(self) -> bool:
        if RESTClient is None:
            logger.error("coinbase-advanced-py not installed")
            return False

        try:
            self.client = RESTClient(
                api_key=self.api_key,
                api_secret=self.secret_key,
            )
            # Test connection
            self.client.get_accounts()
            self._connected = True
            logger.info("Connected to Coinbase data provider")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Coinbase data provider: {e}")
            self._connected = False
            return False

    def disconnect(self) -> None:
        self._connected = False
        logger.info("Disconnected from Coinbase data provider")

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """Ensure symbol is in Coinbase product_id format (e.g., BTC-USD)."""
        if "-" not in symbol:
            return f"{symbol}-USD"
        return symbol

    def get_bars(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> List[Bar]:
        if not self._connected or not self.client:
            raise RuntimeError("Not connected to data provider")

        product_id = self._normalize_symbol(symbol)
        granularity = _GRANULARITY_MAP.get(timeframe.lower().strip())
        if not granularity:
            raise ValueError(
                f"Unsupported timeframe: {timeframe}. "
                f"Supported: {', '.join(_GRANULARITY_MAP.keys())}"
            )

        try:
            # Coinbase expects Unix timestamps
            start_ts = str(int(start.timestamp()))
            end_ts = str(int(end.timestamp()))

            response = self.client.get_candles(
                product_id=product_id,
                start=start_ts,
                end=end_ts,
                granularity=granularity,
            )

            candles = _parse_candles(response)
            bars = []
            for candle in candles:
                ts = int(_g(candle, "start", 0))
                bars.append(Bar(
                    symbol=symbol,
                    timestamp=datetime.fromtimestamp(ts),
                    open=Decimal(str(_g(candle, "open", 0))),
                    high=Decimal(str(_g(candle, "high", 0))),
                    low=Decimal(str(_g(candle, "low", 0))),
                    close=Decimal(str(_g(candle, "close", 0))),
                    volume=int(float(_g(candle, "volume", 0))),
                ))

            bars.sort(key=lambda b: b.timestamp)
            logger.debug(f"Retrieved {len(bars)} bars for {product_id}")
            return bars

        except Exception as e:
            logger.error(f"Failed to get bars for {product_id}: {e}")
            raise

    def get_latest_bar(self, symbol: str) -> Optional[Bar]:
        if not self._connected or not self.client:
            raise RuntimeError("Not connected to data provider")

        product_id = self._normalize_symbol(symbol)
        try:
            response = self.client.get_candles(
                product_id=product_id,
                start=str(int(datetime.now().timestamp()) - 86400),
                end=str(int(datetime.now().timestamp())),
                granularity="ONE_DAY",
            )

            candles = _parse_candles(response)
            if not candles:
                return None

            candle = candles[0]  # Most recent
            ts = int(_g(candle, "start", 0))
            return Bar(
                symbol=symbol,
                timestamp=datetime.fromtimestamp(ts),
                open=Decimal(str(_g(candle, "open", 0))),
                high=Decimal(str(_g(candle, "high", 0))),
                low=Decimal(str(_g(candle, "low", 0))),
                close=Decimal(str(_g(candle, "close", 0))),
                volume=int(float(_g(candle, "volume", 0))),
            )

        except Exception as e:
            logger.error(f"Failed to get latest bar for {product_id}: {e}")
            return None

    def get_latest_quote(self, symbol: str) -> Optional[Quote]:
        if not self._connected or not self.client:
            raise RuntimeError("Not connected to data provider")

        product_id = self._normalize_symbol(symbol)
        try:
            ticker = self.client.get_product(product_id)
            price = Decimal(str(_g(ticker, "price", 0)))
            bid = Decimal(str(_g(ticker, "bid", price)))
            ask = Decimal(str(_g(ticker, "ask", price)))
            if bid > ask:
                bid, ask = ask, bid

            return Quote(
                symbol=symbol,
                timestamp=datetime.now(),
                bid_price=bid,
                ask_price=ask,
                bid_size=0,
                ask_size=0,
            )
        except Exception as e:
            logger.error(f"Failed to get latest quote for {product_id}: {e}")
            return None

    def subscribe_bars(self, symbols: List[str], timeframe: str, callback: Callable[[Bar], None]) -> None:
        logger.info(f"Subscribing to bars for {symbols} (timeframe: {timeframe})")
        for symbol in symbols:
            self._bar_callbacks[symbol] = callback

    def subscribe_quotes(self, symbols: List[str], callback: Callable[[Quote], None]) -> None:
        logger.info(f"Subscribing to quotes for {symbols}")
        for symbol in symbols:
            self._quote_callbacks[symbol] = callback

    def subscribe_trades(self, symbols: List[str], callback: Callable[[Trade], None]) -> None:
        logger.info(f"Subscribing to trades for {symbols}")
        for symbol in symbols:
            self._trade_callbacks[symbol] = callback

    def unsubscribe_bars(self, symbols: List[str]) -> None:
        for symbol in symbols:
            self._bar_callbacks.pop(symbol, None)

    def unsubscribe_quotes(self, symbols: List[str]) -> None:
        for symbol in symbols:
            self._quote_callbacks.pop(symbol, None)

    def unsubscribe_trades(self, symbols: List[str]) -> None:
        for symbol in symbols:
            self._trade_callbacks.pop(symbol, None)
