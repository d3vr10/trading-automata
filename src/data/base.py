from abc import ABC, abstractmethod
from typing import List, Optional, Callable
from datetime import datetime

from .models import Bar, Quote, Trade


class IDataProvider(ABC):
    """Abstract data provider interface.

    Defines the contract for data providers that fetch and stream
    market data (bars, quotes, trades).
    """

    @abstractmethod
    def connect(self) -> bool:
        """Connect to data provider.

        Returns:
            True if connection successful, False otherwise.
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from data provider."""
        pass

    @abstractmethod
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
            timeframe: Bar timeframe ('1min', '5min', '15min', '1h', '1d', etc.)
            start: Start datetime
            end: End datetime

        Returns:
            List of Bar objects.
        """
        pass

    @abstractmethod
    def get_latest_bar(self, symbol: str) -> Optional[Bar]:
        """Get latest bar for symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Latest Bar object or None if unavailable.
        """
        pass

    @abstractmethod
    def get_latest_quote(self, symbol: str) -> Optional[Quote]:
        """Get latest quote for symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Latest Quote object or None if unavailable.
        """
        pass

    @abstractmethod
    def subscribe_bars(
        self,
        symbols: List[str],
        timeframe: str,
        callback: Callable[[Bar], None]
    ) -> None:
        """Subscribe to real-time bar data.

        Args:
            symbols: List of stock symbols
            timeframe: Bar timeframe
            callback: Function called with each Bar update
        """
        pass

    @abstractmethod
    def subscribe_quotes(
        self,
        symbols: List[str],
        callback: Callable[[Quote], None]
    ) -> None:
        """Subscribe to real-time quote data.

        Args:
            symbols: List of stock symbols
            callback: Function called with each Quote update
        """
        pass

    @abstractmethod
    def subscribe_trades(
        self,
        symbols: List[str],
        callback: Callable[[Trade], None]
    ) -> None:
        """Subscribe to real-time trade data.

        Args:
            symbols: List of stock symbols
            callback: Function called with each Trade update
        """
        pass

    @abstractmethod
    def unsubscribe_bars(self, symbols: List[str]) -> None:
        """Unsubscribe from bar data.

        Args:
            symbols: List of stock symbols to unsubscribe from
        """
        pass

    @abstractmethod
    def unsubscribe_quotes(self, symbols: List[str]) -> None:
        """Unsubscribe from quote data.

        Args:
            symbols: List of stock symbols to unsubscribe from
        """
        pass

    @abstractmethod
    def unsubscribe_trades(self, symbols: List[str]) -> None:
        """Unsubscribe from trade data.

        Args:
            symbols: List of stock symbols to unsubscribe from
        """
        pass
