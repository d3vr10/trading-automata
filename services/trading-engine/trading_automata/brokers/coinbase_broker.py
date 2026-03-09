import logging
from typing import List, Optional, Dict, Any
from decimal import Decimal

from .base import IBroker, Environment

try:
    from coinbase.rest import RESTClient
except ImportError:
    RESTClient = None


logger = logging.getLogger(__name__)


class CoinbaseBroker(IBroker):
    """Coinbase broker implementation.

    Provides integration with Coinbase's Advanced Trading API, supporting
    crypto trading on Coinbase exchange.
    """

    def __init__(self, api_key: str, secret_key: str, passphrase: str, environment: Environment):
        """Initialize Coinbase broker.

        Args:
            api_key: Coinbase API key
            secret_key: Coinbase secret key
            passphrase: Coinbase passphrase (additional security layer)
            environment: Trading environment (PAPER or LIVE)

        Raises:
            ImportError: If coinbase-advanced-py is not installed.
        """
        if RESTClient is None:
            raise ImportError(
                "coinbase-advanced-py is required for Coinbase broker. "
                "Install with: pip install coinbase-advanced-py"
            )

        self.environment = environment
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase
        self.client = None
        self._connected = False

    def connect(self) -> bool:
        """Establish connection to Coinbase.

        Returns:
            True if connection successful, False otherwise.
        """
        try:
            # Initialize Coinbase REST client
            self.client = RESTClient(
                api_key=self.api_key,
                api_secret=self.secret_key,
                # Note: Coinbase Advanced Trading doesn't have paper trading mode
                # For testing, use a sub-account with small funds
            )

            # Test connection by fetching account info
            accounts = self.client.get_accounts()
            self._connected = True

            logger.info(
                f"Connected to Coinbase ({self.environment.value} trading). "
                f"Accounts: {len(accounts)}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Coinbase: {e}")
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Disconnect from Coinbase."""
        self._connected = False
        logger.info("Disconnected from Coinbase")

    def get_account(self) -> Dict[str, Any]:
        """Get account information.

        Returns:
            Dictionary with account details.
        """
        if not self._connected:
            raise RuntimeError("Not connected to broker")

        try:
            # Get all accounts
            accounts = self.client.get_accounts()

            # Calculate total portfolio value
            total_value = Decimal('0')
            total_cash = Decimal('0')

            for account in accounts:
                # Available balance in the account
                available = Decimal(str(account.get('available_balance', {}).get('value', '0')))
                total_value += available

                # Check if it's a USD/stablecoin account
                if 'USD' in account.get('currency', '') or 'USDC' in account.get('currency', ''):
                    total_cash += available

            return {
                'account_id': accounts[0].get('id') if accounts else 'unknown',
                'portfolio_value': float(total_value),
                'buying_power': float(total_cash),  # Simplified: USD balance = buying power
                'cash': float(total_cash),
                'last_equity': float(total_value),
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
            accounts = self.client.get_accounts()
            positions = []

            for account in accounts:
                currency = account.get('currency', '')
                available = Decimal(str(account.get('available_balance', {}).get('value', '0')))

                # Only include non-zero positions
                if available > 0 and currency not in ('USD', 'USDC', 'USDT'):
                    positions.append({
                        'symbol': currency,  # Crypto symbol
                        'qty': float(available),
                        'avg_fill_price': 0.0,  # Coinbase doesn't easily provide this
                        'current_price': 0.0,  # Would need separate API call
                        'unrealized_pl': 0.0,
                        'unrealized_plpc': 0.0,
                        'market_value': float(available),
                    })

            return positions

        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            raise

    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get position for specific symbol.

        Args:
            symbol: Crypto symbol (e.g., 'BTC', 'ETH')

        Returns:
            Position dictionary or None if not found.
        """
        if not self._connected:
            raise RuntimeError("Not connected to broker")

        try:
            accounts = self.client.get_accounts()

            for account in accounts:
                if account.get('currency') == symbol:
                    available = Decimal(str(account.get('available_balance', {}).get('value', '0')))
                    if available > 0:
                        return {
                            'symbol': symbol,
                            'qty': float(available),
                            'avg_fill_price': 0.0,
                            'current_price': 0.0,
                            'unrealized_pl': 0.0,
                            'unrealized_plpc': 0.0,
                            'market_value': float(available),
                        }

            return None

        except Exception as e:
            logger.error(f"Failed to get position for {symbol}: {e}")
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
        """Submit an order to Coinbase.

        Args:
            symbol: Crypto symbol (e.g., 'BTC-USD', 'ETH-USD')
            qty: Quantity to trade
            side: 'buy' or 'sell'
            order_type: 'market', 'limit', 'stop'
            time_in_force: 'IOC' (immediate), 'GTC' (good till cancel), 'FOK' (fill or kill)
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
            # Ensure product_id is in correct format (e.g., BTC-USD)
            if '-' not in symbol:
                product_id = f"{symbol}-USD"
            else:
                product_id = symbol

            # Map side
            side_lower = side.lower()
            if side_lower not in ('buy', 'sell'):
                raise ValueError(f"Invalid side: {side}")

            # Map order type and time in force
            order_config = {
                'client_order_id': kwargs.get('client_order_id'),
                'product_id': product_id,
                'side': side_lower,
                'order_configuration': {}
            }

            if order_type.lower() == 'market':
                order_config['order_configuration'] = {
                    'market_market_ioc': {
                        'quote_size': str(qty)  # Size in quote currency (USD)
                    }
                }

            elif order_type.lower() == 'limit':
                if limit_price is None:
                    raise ValueError("limit_price required for limit orders")

                tif = time_in_force.upper() if time_in_force else 'GTC'
                if tif not in ('GTC', 'IOC', 'FOK'):
                    tif = 'GTC'

                order_config['order_configuration'] = {
                    'limit_limit_gtc': {
                        'base_size': str(qty),
                        'limit_price': str(limit_price),
                        'post_only': False
                    }
                }

                if tif == 'IOC':
                    order_config['order_configuration']['limit_limit_gtc']['post_only'] = False
                elif tif == 'FOK':
                    order_config['order_configuration']['limit_limit_gtc']['post_only'] = False

            elif order_type.lower() == 'stop':
                if stop_price is None:
                    raise ValueError("stop_price required for stop orders")

                order_config['order_configuration'] = {
                    'stop_limit_stop_limit_gtc': {
                        'base_size': str(qty),
                        'limit_price': str(limit_price or stop_price),
                        'stop_price': str(stop_price),
                        'post_only': False
                    }
                }

            else:
                raise ValueError(f"Unsupported order type: {order_type}")

            # Submit order
            response = self.client.create_order(**order_config)
            order_id = response.get('success_order_id') or response.get('order_id')

            logger.info(
                f"Order submitted: {order_id} - {side} {qty} {product_id} "
                f"({order_type} @ {limit_price or stop_price or 'market'})"
            )

            return str(order_id)

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
            self.client.cancel_orders(order_ids=[order_id])
            logger.info(f"Order cancelled: {order_id}")
            return True

        except Exception as e:
            logger.warning(f"Failed to cancel order {order_id}: {e}")
            return False

    def close_position(self, symbol: str) -> bool:
        """Close/liquidate the full position for a symbol.

        Coinbase has no native close_position endpoint, so we emulate it
        by submitting a market sell order for the full position quantity.

        Args:
            symbol: Trading symbol (e.g., 'BTC-USD')

        Returns:
            True if closed successfully, False otherwise.
        """
        if not self._connected:
            raise RuntimeError("Not connected to broker")

        try:
            # Get current position
            position = self.get_position(symbol)
            if not position:
                logger.warning(f"No open position for {symbol}")
                return False

            qty = position.get('quantity', 0)
            if qty == 0:
                logger.warning(f"Position quantity is 0 for {symbol}")
                return False

            # Submit market sell order for the full quantity
            order_id = self.submit_order(
                symbol=symbol,
                qty=Decimal(str(qty)),
                side='sell',
                order_type='market',
                time_in_force='IOC'  # Immediate Or Cancel
            )

            logger.info(f"Position closed: {symbol} (order: {order_id})")
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
            # Get all open orders
            orders = self.get_orders(status='open')

            # Filter by symbol if provided
            if symbol:
                orders = [o for o in orders if o['symbol'] == symbol]

            # Extract order IDs
            order_ids = [o['id'] for o in orders]

            if not order_ids:
                logger.info(f"No open orders to cancel{' for ' + symbol if symbol else ''}")
                return []

            # Batch cancel (Coinbase supports up to 100 IDs per request)
            self.client.cancel_orders(order_ids=order_ids)
            logger.info(f"Cancelled {len(order_ids)} orders{' for ' + symbol if symbol else ''}")
            return order_ids

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
            order = self.client.get_order(order_id)

            return {
                'id': str(order.get('order_id')),
                'symbol': order.get('product_id'),
                'qty': float(order.get('order_quantity', {}).get('base_size', 0)),
                'filled_qty': float(order.get('filled_size', 0)),
                'side': order.get('side', 'unknown'),
                'type': order.get('order_type', 'unknown'),
                'status': order.get('status', 'unknown'),
                'created_at': order.get('created_time'),
                'filled_at': order.get('time_in_force'),
                'filled_avg_price': float(order.get('average_filled_price', 0)) if order.get('average_filled_price') else None,
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
            # Coinbase API supports order status filtering
            order_status = None
            if status:
                status_upper = status.upper()
                if status_upper in ('OPEN', 'FILLED', 'CANCELLED', 'EXPIRED', 'FAILED'):
                    order_status = status_upper

            # Fetch orders
            orders = self.client.list_orders(
                order_status=order_status,
                limit=limit
            )

            result = []
            for order in orders.get('orders', []):
                result.append({
                    'id': str(order.get('order_id')),
                    'symbol': order.get('product_id'),
                    'qty': float(order.get('order_quantity', {}).get('base_size', 0)),
                    'filled_qty': float(order.get('filled_size', 0)),
                    'side': order.get('side', 'unknown'),
                    'type': order.get('order_type', 'unknown'),
                    'status': order.get('status', 'unknown'),
                    'created_at': order.get('created_time'),
                    'filled_at': order.get('time_in_force'),
                    'filled_avg_price': float(order.get('average_filled_price', 0)) if order.get('average_filled_price') else None,
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
