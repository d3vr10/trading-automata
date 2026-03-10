from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from decimal import Decimal
from enum import Enum


class Environment(Enum):
    """Trading environment enum"""
    PAPER = "paper"
    LIVE = "live"


class IBroker(ABC):
    """Abstract broker interface for trading operations.

    This interface defines the contract that all broker implementations
    must follow, enabling easy switching between brokers and environments.
    """

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to broker.

        Returns:
            True if connection successful, False otherwise.
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from broker."""
        pass

    @abstractmethod
    def get_account(self) -> Dict[str, Any]:
        """Get account information.

        Returns:
            Dictionary containing account details including:
            - account_id: Account ID
            - portfolio_value: Current portfolio value
            - buying_power: Available buying power
            - cash: Cash balance
            - last_equity: Last equity
        """
        pass

    @abstractmethod
    def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions.

        Returns:
            List of position dictionaries, each containing:
            - symbol: Stock symbol
            - qty: Quantity held
            - avg_fill_price: Average fill price
            - current_price: Current market price
        """
        pass

    @abstractmethod
    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get position for specific symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Position dictionary or None if position doesn't exist.
        """
        pass

    @abstractmethod
    def submit_order(
        self,
        symbol: str,
        qty: Decimal,
        side: str,
        order_type: str,
        time_in_force: str,
        limit_price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        **kwargs
    ) -> str:
        """Submit an order.

        Args:
            symbol: Stock symbol
            qty: Quantity to trade
            side: 'buy' or 'sell'
            order_type: 'market', 'limit', 'stop', 'trailing_stop'
            time_in_force: 'day', 'gtc', 'opg', 'cls', 'ioc', 'fok'
            limit_price: Price for limit orders
            stop_price: Price for stop orders
            **kwargs: Additional broker-specific parameters

        Returns:
            Order ID
        """
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order.

        Args:
            order_id: Order ID to cancel

        Returns:
            True if cancelled, False if order already filled or failed.
        """
        pass

    @abstractmethod
    def close_position(self, symbol: str) -> bool:
        """Close/liquidate the full open position for a symbol.

        Args:
            symbol: Trading symbol (e.g., 'SPY', 'BTC-USD')

        Returns:
            True if position closed successfully, False if no position or failed.
        """
        pass

    @abstractmethod
    def cancel_all_orders(self, symbol: Optional[str] = None) -> List[str]:
        """Cancel all open orders, optionally filtered by symbol.

        Args:
            symbol: Optional symbol to filter orders. If None, cancels all orders.

        Returns:
            List of cancelled order IDs.
        """
        pass

    @abstractmethod
    def get_order(self, order_id: str) -> Dict[str, Any]:
        """Get order details.

        Args:
            order_id: Order ID

        Returns:
            Order dictionary containing status and details.
        """
        pass

    @abstractmethod
    def get_orders(self, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get orders.

        Args:
            status: Filter by status ('open', 'closed', etc.)
            limit: Maximum number of orders to return

        Returns:
            List of order dictionaries.
        """
        pass

    @abstractmethod
    def get_account_snapshot(self) -> Dict[str, Any]:
        """Get a normalized account snapshot for dashboard display.

        Returns a unified format across all brokers with currency-aware values.
        Platforms like 3Commas/Cryptohopper use this pattern: each broker
        reports in its native currency, and the UI normalizes to a display currency.

        Returns:
            Dictionary containing:
            - broker_type: str ("alpaca" or "coinbase")
            - currency: str (base currency, e.g. "USD")
            - equity: float (total account value in base currency)
            - cash: float (available cash/buying power)
            - positions: list of dicts, each with:
                - symbol: str
                - qty: float
                - avg_entry_price: float
                - current_price: float
                - market_value: float (in base currency, e.g. USD)
                - unrealized_pnl: float (in base currency)
                - unrealized_pnl_pct: float
                - currency: str (native currency of the asset)
        """
        pass

    @abstractmethod
    def get_environment(self) -> Environment:
        """Get the current trading environment.

        Returns:
            Environment enum (PAPER or LIVE).
        """
        pass
