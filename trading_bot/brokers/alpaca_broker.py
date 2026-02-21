import logging
from typing import List, Optional, Dict, Any
from decimal import Decimal

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, StopOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderStatus

from .base import IBroker, Environment


logger = logging.getLogger(__name__)


class AlpacaBroker(IBroker):
    """Alpaca broker implementation.

    Provides integration with Alpaca's trading API, supporting both
    paper trading and live trading with the same interface.
    """

    def __init__(self, api_key: str, secret_key: str, environment: Environment):
        """Initialize Alpaca broker.

        Args:
            api_key: Alpaca API key
            secret_key: Alpaca secret key
            environment: Trading environment (PAPER or LIVE)
        """
        self.environment = environment
        self.api_key = api_key
        self.secret_key = secret_key
        self.client = None
        self._connected = False

    def connect(self) -> bool:
        """Establish connection to Alpaca.

        Returns:
            True if connection successful, False otherwise.
        """
        try:
            self.client = TradingClient(
                api_key=self.api_key,
                secret_key=self.secret_key,
                paper=self.environment == Environment.PAPER
            )
            # Test connection by fetching account
            account = self.client.get_account()
            self._connected = True
            logger.info(
                f"Connected to Alpaca ({self.environment.value} trading). "
                f"Account: {account.account_number}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Alpaca: {e}")
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Disconnect from Alpaca."""
        self._connected = False
        logger.info("Disconnected from Alpaca")

    def get_account(self) -> Dict[str, Any]:
        """Get account information.

        Returns:
            Dictionary with account details.
        """
        if not self._connected:
            raise RuntimeError("Not connected to broker")

        try:
            account = self.client.get_account()
            return {
                'account_id': account.id,
                'portfolio_value': float(account.portfolio_value),
                'buying_power': float(account.buying_power),
                'cash': float(account.cash),
                'last_equity': float(account.last_equity),
                'account_number': account.account_number,
            }
        except Exception as e:
            logger.error(f"Failed to get account information: {e}")
            raise

    def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions.

        Returns:
            List of position dictionaries.
        """
        if not self._connected:
            raise RuntimeError("Not connected to broker")

        try:
            positions = self.client.get_all_positions()
            result = []
            for pos in positions:
                # Handle different attribute names across alpaca-py versions
                avg_fill_price = getattr(pos, 'avg_fill_price', None) or getattr(pos, 'avg_entry_price', 0)

                result.append({
                    'symbol': pos.symbol,
                    'qty': float(pos.qty),
                    'avg_fill_price': float(avg_fill_price) if avg_fill_price else 0,
                    'current_price': float(pos.current_price),
                    'unrealized_pl': float(pos.unrealized_pl),
                    'unrealized_plpc': float(pos.unrealized_plpc),
                    'market_value': float(pos.market_value),
                })
            return result
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            raise

    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get position for specific symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Position dictionary or None if not found.
        """
        if not self._connected:
            raise RuntimeError("Not connected to broker")

        try:
            pos = self.client.get_position(symbol)
            # Handle different attribute names across alpaca-py versions
            avg_fill_price = getattr(pos, 'avg_fill_price', None) or getattr(pos, 'avg_entry_price', 0)

            return {
                'symbol': pos.symbol,
                'qty': float(pos.qty),
                'avg_fill_price': float(avg_fill_price) if avg_fill_price else 0,
                'current_price': float(pos.current_price),
                'unrealized_pl': float(pos.unrealized_pl),
                'unrealized_plpc': float(pos.unrealized_plpc),
                'market_value': float(pos.market_value),
            }
        except Exception:
            return None

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
            qty: Quantity
            side: 'buy' or 'sell'
            order_type: 'market', 'limit', 'stop'
            time_in_force: 'day', 'gtc', 'opg', 'cls', 'ioc', 'fok'
            limit_price: Price for limit orders
            stop_price: Price for stop orders
            **kwargs: Additional parameters

        Returns:
            Order ID

        Raises:
            ValueError: If parameters are invalid.
        """
        if not self._connected:
            raise RuntimeError("Not connected to broker")

        try:
            order_side = OrderSide.BUY if side.lower() == 'buy' else OrderSide.SELL

            # Map time_in_force to TimeInForce enum
            # Valid values: day, gtc, opg, cls, ioc, fok
            tif_map = {
                'day': TimeInForce.DAY,
                'gtc': TimeInForce.GTC,
                'opg': TimeInForce.OPG,
                'cls': TimeInForce.CLS,
                'ioc': TimeInForce.IOC,
                'fok': TimeInForce.FOK,
            }
            tif = tif_map.get(time_in_force.lower(), TimeInForce.DAY)

            if order_type.lower() == 'market':
                order_request = MarketOrderRequest(
                    symbol=symbol,
                    qty=float(qty),
                    side=order_side,
                    time_in_force=tif,
                )
            elif order_type.lower() == 'limit':
                if limit_price is None:
                    raise ValueError("limit_price required for limit orders")
                order_request = LimitOrderRequest(
                    symbol=symbol,
                    qty=float(qty),
                    side=order_side,
                    limit_price=float(limit_price),
                    time_in_force=tif,
                )
            elif order_type.lower() == 'stop':
                if stop_price is None:
                    raise ValueError("stop_price required for stop orders")
                order_request = StopOrderRequest(
                    symbol=symbol,
                    qty=float(qty),
                    side=order_side,
                    stop_price=float(stop_price),
                    time_in_force=tif,
                )
            else:
                raise ValueError(f"Unsupported order type: {order_type}")

            order = self.client.submit_order(order_request)
            logger.info(
                f"Order submitted: {order.id} - {side} {qty} {symbol} "
                f"({order_type} @ {limit_price or stop_price or 'market'})"
            )
            return str(order.id)

        except Exception as e:
            logger.error(f"Failed to submit order: {e}")
            raise

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order.

        Args:
            order_id: Order ID to cancel

        Returns:
            True if cancelled, False otherwise.
        """
        if not self._connected:
            raise RuntimeError("Not connected to broker")

        try:
            self.client.cancel_order_by_id(order_id)
            logger.info(f"Order cancelled: {order_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to cancel order {order_id}: {e}")
            return False

    def close_position(self, symbol: str) -> bool:
        """Close/liquidate the full position for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            True if closed successfully, False otherwise.
        """
        if not self._connected:
            raise RuntimeError("Not connected to broker")

        try:
            self.client.close_position(symbol_or_asset_id=symbol)
            logger.info(f"Position closed: {symbol}")
            return True
        except Exception as e:
            logger.warning(f"Failed to close position {symbol}: {e}")
            return False

    def cancel_all_orders(self, symbol: Optional[str] = None) -> List[str]:
        """Cancel all open orders, optionally for a specific symbol.

        Args:
            symbol: Optional symbol to filter cancellations

        Returns:
            List of cancelled order IDs.
        """
        if not self._connected:
            raise RuntimeError("Not connected to broker")

        try:
            if symbol:
                # Get all open orders and filter by symbol
                orders = self.get_orders(status='open')
                symbol_orders = [o for o in orders if o['symbol'] == symbol]
                cancelled = []
                for order in symbol_orders:
                    if self.cancel_order(order['id']):
                        cancelled.append(order['id'])
                logger.info(f"Cancelled {len(cancelled)} orders for {symbol}")
                return cancelled
            else:
                # Cancel all orders using Alpaca's batch cancel
                cancellation_results = self.client.cancel_orders()
                cancelled = [str(result.id) for result in cancellation_results if result]
                logger.info(f"Cancelled {len(cancelled)} orders")
                return cancelled
        except Exception as e:
            logger.error(f"Failed to cancel orders: {e}")
            return []

    def get_order(self, order_id: str) -> Dict[str, Any]:
        """Get order details.

        Args:
            order_id: Order ID

        Returns:
            Order dictionary with details.
        """
        if not self._connected:
            raise RuntimeError("Not connected to broker")

        try:
            order = self.client.get_order_by_id(order_id)
            return {
                'id': str(order.id),
                'symbol': order.symbol,
                'qty': float(order.qty),
                'filled_qty': float(order.filled_qty),
                'side': order.side.value,
                'type': order.order_type.value,
                'status': order.status.value,
                'created_at': order.created_at.isoformat(),
                'filled_at': order.filled_at.isoformat() if order.filled_at else None,
                'filled_avg_price': float(order.filled_avg_price) if order.filled_avg_price else None,
            }
        except Exception as e:
            logger.error(f"Failed to get order {order_id}: {e}")
            raise

    def get_orders(self, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get orders.

        Args:
            status: Filter by status ('open', 'closed', etc.)
            limit: Maximum orders to return

        Returns:
            List of order dictionaries.
        """
        if not self._connected:
            raise RuntimeError("Not connected to broker")

        try:
            # Map status names to Alpaca OrderStatus enum if provided
            if status:
                status_enum = OrderStatus(status.upper())
                orders = self.client.get_orders(status=status_enum)
            else:
                orders = self.client.get_orders()

            result = []
            # Limit results to the requested amount
            for order in orders[:limit]:
                result.append({
                    'id': str(order.id),
                    'symbol': order.symbol,
                    'qty': float(order.qty),
                    'filled_qty': float(order.filled_qty),
                    'side': order.side.value,
                    'type': order.order_type.value,
                    'status': order.status.value,
                    'created_at': order.created_at.isoformat(),
                    'filled_at': order.filled_at.isoformat() if order.filled_at else None,
                    'filled_avg_price': float(order.filled_avg_price) if order.filled_avg_price else None,
                })
            return result
        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            raise

    def get_environment(self) -> Environment:
        """Get current trading environment.

        Returns:
            Environment enum.
        """
        return self.environment
