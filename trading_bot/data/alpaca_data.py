import logging
from typing import List, Optional, Callable
from datetime import datetime
from decimal import Decimal

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestBarRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.live import StockDataStream

from .base import IDataProvider
from .models import Bar, Quote, Trade


logger = logging.getLogger(__name__)


class AlpacaDataProvider(IDataProvider):
    """Alpaca data provider implementation.

    Provides historical and real-time market data through Alpaca's
    data APIs.
    """

    def __init__(self, api_key: str, secret_key: str):
        """Initialize Alpaca data provider.

        Args:
            api_key: Alpaca API key
            secret_key: Alpaca secret key
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.historical_client = None
        self.stream_client = None
        self._connected = False
        self._bar_callbacks = {}
        self._quote_callbacks = {}
        self._trade_callbacks = {}

    def connect(self) -> bool:
        """Connect to Alpaca data API.

        Returns:
            True if successful, False otherwise.
        """
        try:
            self.historical_client = StockHistoricalDataClient(
                self.api_key,
                self.secret_key
            )
            self._connected = True
            logger.info("Connected to Alpaca data provider")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Alpaca data provider: {e}")
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Disconnect from data provider."""
        if self.stream_client:
            try:
                self.stream_client.close()
            except Exception as e:
                logger.warning(f"Error closing stream client: {e}")
        self._connected = False
        logger.info("Disconnected from Alpaca data provider")

    def get_bars(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime
    ) -> List[Bar]:
        """Get historical bars.

        Args:
            symbol: Stock symbol
            timeframe: Timeframe string ('1min', '5min', '15min', '1h', '1d', etc.)
            start: Start datetime
            end: End datetime

        Returns:
            List of Bar objects.
        """
        if not self._connected or not self.historical_client:
            raise RuntimeError("Not connected to data provider")

        try:
            # Convert timeframe string to TimeFrame enum
            tf = self._parse_timeframe(timeframe)

            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=tf,
                start=start,
                end=end,
            )

            bars_data = self.historical_client.get_stock_bars(request)

            bars = []
            if symbol in bars_data:
                for bar in bars_data[symbol]:
                    bars.append(Bar(
                        symbol=symbol,
                        timestamp=bar.timestamp,
                        open=Decimal(str(bar.open)),
                        high=Decimal(str(bar.high)),
                        low=Decimal(str(bar.low)),
                        close=Decimal(str(bar.close)),
                        volume=int(bar.volume),
                    ))

            logger.debug(f"Retrieved {len(bars)} bars for {symbol}")
            return bars

        except Exception as e:
            logger.error(f"Failed to get bars for {symbol}: {e}")
            raise

    def get_latest_bar(self, symbol: str) -> Optional[Bar]:
        """Get latest bar for symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Latest Bar or None if unavailable.
        """
        if not self._connected or not self.historical_client:
            raise RuntimeError("Not connected to data provider")

        try:
            request = StockLatestBarRequest(symbol_or_symbols=symbol)
            bars_data = self.historical_client.get_stock_latest_bar(request)

            if symbol in bars_data and bars_data[symbol]:
                bar = bars_data[symbol]
                return Bar(
                    symbol=symbol,
                    timestamp=bar.timestamp,
                    open=Decimal(str(bar.open)),
                    high=Decimal(str(bar.high)),
                    low=Decimal(str(bar.low)),
                    close=Decimal(str(bar.close)),
                    volume=int(bar.volume),
                )
            return None

        except Exception as e:
            logger.error(f"Failed to get latest bar for {symbol}: {e}")
            return None

    def get_latest_quote(self, symbol: str) -> Optional[Quote]:
        """Get latest quote for symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Latest Quote or None if unavailable.
        """
        if not self._connected or not self.historical_client:
            raise RuntimeError("Not connected to data provider")

        try:
            request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
            quotes_data = self.historical_client.get_stock_latest_quote(request)

            if symbol in quotes_data and quotes_data[symbol]:
                quote = quotes_data[symbol]
                return Quote(
                    symbol=symbol,
                    timestamp=quote.timestamp,
                    bid_price=Decimal(str(quote.bid_price)),
                    ask_price=Decimal(str(quote.ask_price)),
                    bid_size=int(quote.bid_size),
                    ask_size=int(quote.ask_size),
                )
            return None

        except Exception as e:
            logger.error(f"Failed to get latest quote for {symbol}: {e}")
            return None

    def subscribe_bars(
        self,
        symbols: List[str],
        timeframe: str,
        callback: Callable[[Bar], None]
    ) -> None:
        """Subscribe to real-time bar data.

        Args:
            symbols: List of symbols
            timeframe: Timeframe for bars
            callback: Function to call with each bar
        """
        logger.info(f"Subscribing to bars for {symbols} (timeframe: {timeframe})")
        for symbol in symbols:
            self._bar_callbacks[symbol] = callback

    def subscribe_quotes(
        self,
        symbols: List[str],
        callback: Callable[[Quote], None]
    ) -> None:
        """Subscribe to real-time quote data.

        Args:
            symbols: List of symbols
            callback: Function to call with each quote
        """
        logger.info(f"Subscribing to quotes for {symbols}")
        for symbol in symbols:
            self._quote_callbacks[symbol] = callback

    def subscribe_trades(
        self,
        symbols: List[str],
        callback: Callable[[Trade], None]
    ) -> None:
        """Subscribe to real-time trade data.

        Args:
            symbols: List of symbols
            callback: Function to call with each trade
        """
        logger.info(f"Subscribing to trades for {symbols}")
        for symbol in symbols:
            self._trade_callbacks[symbol] = callback

    def unsubscribe_bars(self, symbols: List[str]) -> None:
        """Unsubscribe from bar data.

        Args:
            symbols: List of symbols to unsubscribe from
        """
        for symbol in symbols:
            self._bar_callbacks.pop(symbol, None)
        logger.info(f"Unsubscribed from bars for {symbols}")

    def unsubscribe_quotes(self, symbols: List[str]) -> None:
        """Unsubscribe from quote data.

        Args:
            symbols: List of symbols to unsubscribe from
        """
        for symbol in symbols:
            self._quote_callbacks.pop(symbol, None)
        logger.info(f"Unsubscribed from quotes for {symbols}")

    def unsubscribe_trades(self, symbols: List[str]) -> None:
        """Unsubscribe from trade data.

        Args:
            symbols: List of symbols to unsubscribe from
        """
        for symbol in symbols:
            self._trade_callbacks.pop(symbol, None)
        logger.info(f"Unsubscribed from trades for {symbols}")

    @staticmethod
    def _parse_timeframe(timeframe: str) -> TimeFrame:
        """Convert timeframe string to TimeFrame enum.

        Args:
            timeframe: Timeframe string ('1min', '5min', '15min', '1h', '1d', etc.)

        Returns:
            TimeFrame enum value.

        Raises:
            ValueError: If timeframe is not recognized.
        """
        timeframe = timeframe.lower().strip()

        if timeframe == '1min':
            return TimeFrame.One_Minute
        elif timeframe == '5min':
            return TimeFrame.Five_Minute
        elif timeframe == '15min':
            return TimeFrame.Fifteen_Minute
        elif timeframe in ('30min', '30'):
            return TimeFrame.Thirty_Minute
        elif timeframe in ('1h', '60min', '60'):
            return TimeFrame.One_Hour
        elif timeframe in ('1d', 'day'):
            return TimeFrame.One_Day
        elif timeframe in ('1w', 'week'):
            return TimeFrame.One_Week
        elif timeframe in ('1mo', 'month'):
            return TimeFrame.One_Month
        else:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
