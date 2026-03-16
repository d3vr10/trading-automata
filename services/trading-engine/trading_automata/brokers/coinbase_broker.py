import logging
import time
from typing import List, Optional, Dict, Any
from decimal import Decimal

from .base import IBroker, Environment

try:
    from coinbase.rest import RESTClient
except ImportError:
    RESTClient = None


logger = logging.getLogger(__name__)


def _g(obj, key, default=None):
    """Safely get a value from a dict or SDK response object.

    The coinbase-advanced-py SDK returns response objects that support
    bracket access (obj['key'] -> None if missing) but NOT .get().
    """
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    try:
        val = obj[key]
        return val if val is not None else default
    except (KeyError, TypeError, IndexError):
        return default


class CoinbaseBroker(IBroker):
    """Coinbase broker implementation.

    Provides integration with Coinbase's Advanced Trading API, supporting
    crypto trading on Coinbase exchange.
    """

    # Cache spot prices for 10 seconds to avoid hammering rate limits
    _PRICE_CACHE_TTL = 10

    def __init__(self, api_key: str, secret_key: str, passphrase: str = "", environment: Environment = Environment.LIVE):
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
        self._price_cache: Dict[str, tuple[float, float]] = {}  # symbol -> (price, timestamp)

    def connect(self) -> bool:
        try:
            if self.environment.value == "paper":
                logger.warning(
                    "Coinbase does not offer a sandbox/paper-trading environment. "
                    "All orders will execute on the LIVE market. "
                    "Use a sub-account with minimal funds for testing."
                )

            self.client = RESTClient(
                api_key=self.api_key,
                api_secret=self.secret_key,
            )

            # Test connection by fetching account info
            accounts = self.client.get_accounts()
            self._connected = True

            account_list = self._parse_accounts(accounts)
            logger.info(
                f"Connected to Coinbase (LIVE trading). "
                f"Accounts: {len(account_list)}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Coinbase: {e}")
            self._last_connect_error = str(e)
            self._connected = False
            return False

    def disconnect(self) -> None:
        self._connected = False
        logger.info("Disconnected from Coinbase")

    def _get_spot_price(self, currency: str) -> float:
        """Get current USD spot price with caching."""
        now = time.monotonic()
        cached = self._price_cache.get(currency)
        if cached and (now - cached[1]) < self._PRICE_CACHE_TTL:
            return cached[0]

        try:
            product_id = f"{currency}-USD"
            ticker = self.client.get_product(product_id)
            price = float(_g(ticker, 'price', 0))
            self._price_cache[currency] = (price, now)
            return price
        except Exception:
            try:
                product_id = f"{currency}-USDC"
                ticker = self.client.get_product(product_id)
                price = float(_g(ticker, 'price', 0))
                self._price_cache[currency] = (price, now)
                return price
            except Exception:
                logger.debug(f"No USD price available for {currency}")
                return 0.0

    def _parse_accounts(self, accounts_response) -> list:
        """Extract account list from API response (handles SDK object, dict, or list)."""
        if isinstance(accounts_response, dict):
            return accounts_response.get('accounts', [])
        if isinstance(accounts_response, list):
            return accounts_response
        # SDK response object (e.g. ListAccountsResponse) — try .accounts attribute
        if hasattr(accounts_response, 'accounts'):
            accts = accounts_response.accounts
            return list(accts) if accts else []
        return []

    def get_account(self) -> Dict[str, Any]:
        if not self._connected:
            raise RuntimeError("Not connected to broker")

        try:
            accounts = self._parse_accounts(self.client.get_accounts())
            total_value = Decimal('0')
            total_cash = Decimal('0')
            stablecoins = {'USD', 'USDC', 'USDT', 'DAI', 'BUSD'}

            for account in accounts:
                currency = _g(account, 'currency', '')
                available = Decimal(str(_g(_g(account, 'available_balance'), 'value', '0')))
                hold = Decimal(str(_g(_g(account, 'hold'), 'value', '0')))
                total_balance = available + hold

                if total_balance <= 0:
                    continue

                if currency in stablecoins:
                    total_value += total_balance
                    total_cash += total_balance
                else:
                    usd_price = self._get_spot_price(currency)
                    total_value += Decimal(str(float(total_balance) * usd_price))

            return {
                'account_id': _g(accounts[0], 'uuid', 'unknown') if accounts else 'unknown',
                'portfolio_value': float(total_value),
                'buying_power': float(total_cash),
                'cash': float(total_cash),
                'last_equity': float(total_value),
            }

        except Exception as e:
            logger.error(f"Failed to get account information: {e}")
            raise

    def get_positions(self) -> List[Dict[str, Any]]:
        if not self._connected:
            raise RuntimeError("Not connected to broker")

        try:
            accounts = self._parse_accounts(self.client.get_accounts())
            positions = []
            stablecoins = {'USD', 'USDC', 'USDT', 'DAI', 'BUSD'}

            for account in accounts:
                currency = _g(account, 'currency', '')
                available = Decimal(str(_g(_g(account, 'available_balance'), 'value', '0')))
                hold = Decimal(str(_g(_g(account, 'hold'), 'value', '0')))
                total_balance = available + hold

                if total_balance <= 0 or currency in stablecoins:
                    continue

                current_price = self._get_spot_price(currency)
                market_value = float(total_balance) * current_price

                positions.append({
                    'symbol': currency,
                    'qty': float(total_balance),
                    'avg_fill_price': 0.0,  # Coinbase doesn't provide cost basis via API
                    'current_price': current_price,
                    'unrealized_pl': 0.0,  # No cost basis available
                    'unrealized_plpc': 0.0,
                    'market_value': market_value,
                })

            return positions

        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            raise

    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self._connected:
            raise RuntimeError("Not connected to broker")

        try:
            accounts = self._parse_accounts(self.client.get_accounts())

            for account in accounts:
                if _g(account, 'currency') == symbol:
                    available = Decimal(str(_g(_g(account, 'available_balance'), 'value', '0')))
                    hold = Decimal(str(_g(_g(account, 'hold'), 'value', '0')))
                    total_balance = available + hold

                    if total_balance > 0:
                        current_price = self._get_spot_price(symbol)
                        return {
                            'symbol': symbol,
                            'qty': float(total_balance),
                            'avg_fill_price': 0.0,
                            'current_price': current_price,
                            'unrealized_pl': 0.0,
                            'unrealized_plpc': 0.0,
                            'market_value': float(total_balance) * current_price,
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
            qty: Quantity in base currency (e.g., 0.1 BTC)
            side: 'buy' or 'sell'
            order_type: 'market', 'limit', 'stop'
            time_in_force: 'IOC', 'GTC', 'FOK'
            limit_price: Price for limit orders
            stop_price: Price for stop orders
        """
        if not self._connected:
            raise RuntimeError("Not connected to broker")

        try:
            # Ensure product_id is in correct format (e.g., BTC-USD)
            if '-' not in symbol:
                product_id = f"{symbol}-USD"
            else:
                product_id = symbol

            side_lower = side.lower()
            if side_lower not in ('buy', 'sell'):
                raise ValueError(f"Invalid side: {side}")

            # Normalize TIF
            tif = time_in_force.upper() if time_in_force else 'GTC'
            if tif not in ('GTC', 'IOC', 'FOK'):
                tif = 'GTC'

            # Build order configuration
            order_config: Dict[str, Any] = {}

            if order_type.lower() == 'market':
                # Market orders: use base_size (asset qty) for both buy and sell
                # Coinbase also supports quote_size (USD amount) for buys,
                # but base_size is consistent with how Alpaca and our engine work
                order_config = {
                    'market_market_ioc': {
                        'base_size': str(qty)
                    }
                }

            elif order_type.lower() == 'limit':
                if limit_price is None:
                    raise ValueError("limit_price required for limit orders")

                # Use the correct config key based on TIF
                if tif == 'IOC':
                    order_config = {
                        'limit_limit_ioc': {
                            'base_size': str(qty),
                            'limit_price': str(limit_price),
                        }
                    }
                elif tif == 'FOK':
                    order_config = {
                        'limit_limit_fok': {
                            'base_size': str(qty),
                            'limit_price': str(limit_price),
                        }
                    }
                else:  # GTC
                    order_config = {
                        'limit_limit_gtc': {
                            'base_size': str(qty),
                            'limit_price': str(limit_price),
                            'post_only': kwargs.get('post_only', False),
                        }
                    }

            elif order_type.lower() == 'stop':
                if stop_price is None:
                    raise ValueError("stop_price required for stop orders")

                # Stop-limit: use stop_price as trigger, limit_price for execution
                effective_limit = str(limit_price) if limit_price else str(stop_price)

                if tif == 'IOC':
                    config_key = 'stop_limit_stop_limit_ioc'
                elif tif == 'FOK':
                    config_key = 'stop_limit_stop_limit_fok'
                else:
                    config_key = 'stop_limit_stop_limit_gtc'

                order_config = {
                    config_key: {
                        'base_size': str(qty),
                        'limit_price': effective_limit,
                        'stop_price': str(stop_price),
                    }
                }

            else:
                raise ValueError(f"Unsupported order type: {order_type}")

            # Submit order
            response = self.client.create_order(
                client_order_id=kwargs.get('client_order_id'),
                product_id=product_id,
                side=side_lower,
                order_configuration=order_config,
            )

            order_id = _g(_g(response, 'success_response'), 'order_id') or _g(response, 'order_id')

            logger.info(
                f"Order submitted: {order_id} - {side} {qty} {product_id} "
                f"({order_type}/{tif} @ {limit_price or stop_price or 'market'})"
            )

            return str(order_id)

        except Exception as e:
            error_str = str(e).lower()
            if '401' in error_str or 'unauthorized' in error_str:
                self._last_connect_error = str(e)
            elif '403' in error_str or 'forbidden' in error_str:
                self._last_connect_error = str(e)
            logger.error(f"Failed to submit order: {e}")
            raise

    def cancel_order(self, order_id: str) -> bool:
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

        Uses a market sell order with base_size (asset quantity).
        """
        if not self._connected:
            raise RuntimeError("Not connected to broker")

        try:
            # Strip -USD suffix for position lookup
            base_symbol = symbol.split('-')[0] if '-' in symbol else symbol
            position = self.get_position(base_symbol)
            if not position:
                logger.warning(f"No open position for {symbol}")
                return False

            qty = position.get('qty', 0)
            if qty == 0:
                logger.warning(f"Position quantity is 0 for {symbol}")
                return False

            order_id = self.submit_order(
                symbol=symbol,
                qty=Decimal(str(qty)),
                side='sell',
                order_type='market',
                time_in_force='IOC'
            )

            logger.info(f"Position closed: {symbol} (order: {order_id})")
            return True

        except Exception as e:
            logger.warning(f"Failed to close position {symbol}: {e}")
            return False

    def cancel_all_orders(self, symbol: Optional[str] = None) -> List[str]:
        if not self._connected:
            raise RuntimeError("Not connected to broker")

        try:
            orders = self.get_orders(status='open')

            if symbol:
                orders = [o for o in orders if o['symbol'] == symbol]

            order_ids = [o['id'] for o in orders]

            if not order_ids:
                logger.info(f"No open orders to cancel{' for ' + symbol if symbol else ''}")
                return []

            self.client.cancel_orders(order_ids=order_ids)
            logger.info(f"Cancelled {len(order_ids)} orders{' for ' + symbol if symbol else ''}")
            return order_ids

        except Exception as e:
            logger.error(f"Failed to cancel orders: {e}")
            return []

    def _parse_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a Coinbase order response into normalized format."""
        # Extract quantity from order_configuration
        qty = 0.0
        order_config = _g(order, 'order_configuration', {})
        if isinstance(order_config, dict):
            config_items = order_config.values()
        elif hasattr(order_config, '__dict__'):
            config_items = [v for v in vars(order_config).values() if v is not None]
        else:
            config_items = []
        for config_type in config_items:
            base = _g(config_type, 'base_size')
            if base is not None:
                qty = float(base)
                break
            quote = _g(config_type, 'quote_size')
            if quote is not None:
                qty = float(quote)
                break

        return {
            'id': str(_g(order, 'order_id', '')),
            'symbol': _g(order, 'product_id', ''),
            'qty': qty,
            'filled_qty': float(_g(order, 'filled_size', 0) or 0),
            'side': _g(order, 'side', 'unknown'),
            'type': _g(order, 'order_type', 'unknown'),
            'status': _g(order, 'status', 'unknown'),
            'created_at': _g(order, 'created_time'),
            'filled_at': _g(order, 'last_fill_time'),
            'filled_avg_price': float(_g(order, 'average_filled_price', 0) or 0) or None,
        }

    def get_order(self, order_id: str) -> Dict[str, Any]:
        if not self._connected:
            raise RuntimeError("Not connected to broker")

        try:
            order = self.client.get_order(order_id)
            inner = _g(order, 'order')
            if inner is not None:
                order = inner
            return self._parse_order(order)

        except Exception as e:
            logger.error(f"Failed to get order {order_id}: {e}")
            raise

    def get_orders(self, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        if not self._connected:
            raise RuntimeError("Not connected to broker")

        try:
            order_status = None
            if status:
                status_upper = status.upper()
                if status_upper in ('OPEN', 'FILLED', 'CANCELLED', 'EXPIRED', 'FAILED'):
                    order_status = status_upper

            response = self.client.list_orders(
                order_status=order_status,
                limit=limit
            )

            orders_list = _g(response, 'orders') or []
            if not isinstance(orders_list, list) and hasattr(orders_list, '__iter__'):
                orders_list = list(orders_list)
            return [self._parse_order(order) for order in orders_list]

        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            raise

    def get_account_snapshot(self) -> Dict[str, Any]:
        """Get normalized account snapshot.

        Uses cached spot prices to stay within rate limits.
        """
        if not self._connected:
            raise RuntimeError("Not connected to broker")

        try:
            accounts = self._parse_accounts(self.client.get_accounts())

            total_equity = Decimal('0')
            total_cash = Decimal('0')
            positions = []
            stablecoins = {'USD', 'USDC', 'USDT', 'DAI', 'BUSD'}

            for account in accounts:
                currency = _g(account, 'currency', '')
                available = Decimal(str(
                    _g(_g(account, 'available_balance'), 'value', '0')
                ))
                hold = Decimal(str(
                    _g(_g(account, 'hold'), 'value', '0')
                ))
                total_balance = available + hold

                if total_balance <= 0:
                    continue

                if currency in stablecoins:
                    usd_value = float(total_balance)
                    total_cash += total_balance
                    total_equity += total_balance
                else:
                    usd_price = self._get_spot_price(currency)
                    usd_value = float(total_balance) * usd_price
                    total_equity += Decimal(str(usd_value))

                    if usd_price > 0:
                        positions.append({
                            'symbol': currency,
                            'qty': float(total_balance),
                            'avg_entry_price': 0.0,  # Coinbase doesn't provide cost basis via API
                            'current_price': usd_price,
                            'market_value': usd_value,
                            'unrealized_pnl': 0.0,
                            'unrealized_pnl_pct': 0.0,
                            'currency': currency,
                        })

            return {
                'broker_type': 'coinbase',
                'currency': 'USD',
                'equity': float(total_equity),
                'cash': float(total_cash),
                'positions': positions,
            }
        except Exception as e:
            error_str = str(e).lower()
            if '401' in error_str or '403' in error_str or 'unauthorized' in error_str or 'forbidden' in error_str:
                self._last_connect_error = str(e)
            logger.error(f"Failed to get account snapshot: {e}")
            raise

    def get_environment(self) -> Environment:
        return self.environment
