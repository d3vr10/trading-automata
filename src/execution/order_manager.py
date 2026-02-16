import logging
from typing import Dict, Optional, List
from decimal import Decimal
from datetime import datetime

from src.brokers.base import IBroker
from src.strategies.base import Signal


logger = logging.getLogger(__name__)


class OrderManager:
    """Manages order execution and tracking.

    Handles submitting orders to the broker, tracking pending orders,
    and processing order fills.
    """

    def __init__(self, broker: IBroker):
        """Initialize order manager.

        Args:
            broker: Broker instance to use for order execution
        """
        self.broker = broker
        self.pending_orders = {}  # Track pending orders
        self.order_history = []   # Historical record of all orders

    def execute_signal(self, signal: Signal) -> Optional[str]:
        """Execute a trading signal by submitting an order.

        Args:
            signal: Trading signal to execute

        Returns:
            Order ID if successful, None otherwise.
        """
        if signal.action == 'hold':
            logger.debug(f"Ignoring HOLD signal for {signal.symbol}")
            return None

        try:
            if signal.action == 'buy':
                order_id = self._submit_buy_order(signal)
            elif signal.action == 'sell':
                order_id = self._submit_sell_order(signal)
            else:
                logger.warning(f"Unknown signal action: {signal.action}")
                return None

            if order_id:
                self.pending_orders[order_id] = {
                    'signal': signal,
                    'status': 'pending',
                    'submitted_at': datetime.now(),
                }
                logger.info(f"Order submitted: {order_id} for signal {signal}")
                return order_id

            return None

        except Exception as e:
            logger.error(f"Failed to execute signal {signal}: {e}")
            return None

    def _submit_buy_order(self, signal: Signal) -> Optional[str]:
        """Submit a buy order.

        Args:
            signal: Buy signal

        Returns:
            Order ID or None if failed.
        """
        try:
            order_id = self.broker.submit_order(
                symbol=signal.symbol,
                qty=signal.quantity,
                side='buy',
                order_type='market',
                time_in_force='day',
            )
            return order_id
        except Exception as e:
            logger.error(f"Failed to submit buy order for {signal.symbol}: {e}")
            return None

    def _submit_sell_order(self, signal: Signal) -> Optional[str]:
        """Submit a sell order.

        Args:
            signal: Sell signal

        Returns:
            Order ID or None if failed.
        """
        try:
            order_id = self.broker.submit_order(
                symbol=signal.symbol,
                qty=signal.quantity,
                side='sell',
                order_type='market',
                time_in_force='day',
            )
            return order_id
        except Exception as e:
            logger.error(f"Failed to submit sell order for {signal.symbol}: {e}")
            return None

    def check_order_status(self, order_id: str) -> Dict:
        """Check status of a pending order.

        Args:
            order_id: Order ID to check

        Returns:
            Order status dictionary.
        """
        try:
            return self.broker.get_order(order_id)
        except Exception as e:
            logger.error(f"Failed to check order status for {order_id}: {e}")
            return {}

    def update_pending_orders(self) -> List[str]:
        """Update status of all pending orders.

        Checks pending orders and moves filled/cancelled orders
        to order history.

        Returns:
            List of order IDs that were completed.
        """
        completed_orders = []

        for order_id in list(self.pending_orders.keys()):
            try:
                order_info = self.check_order_status(order_id)

                # Alpaca returns order status as a string value
                status = order_info.get('status', '').upper()

                if status in ('FILLED', 'PARTIALLY_FILLED', 'CANCELLED', 'EXPIRED', 'REJECTED'):
                    # Move to history
                    pending = self.pending_orders.pop(order_id)
                    pending['final_status'] = status
                    pending['completed_at'] = datetime.now()
                    pending['final_info'] = order_info
                    self.order_history.append(pending)

                    completed_orders.append(order_id)
                    logger.info(
                        f"Order {order_id} completed with status: {status}"
                    )

            except Exception as e:
                logger.warning(f"Failed to update order {order_id}: {e}")

        return completed_orders

    def get_pending_orders(self) -> List[str]:
        """Get list of pending order IDs.

        Returns:
            List of pending order IDs.
        """
        return list(self.pending_orders.keys())

    def get_order_history(self) -> List[Dict]:
        """Get historical record of executed orders.

        Returns:
            List of completed order records.
        """
        return self.order_history.copy()

    def get_stats(self) -> Dict:
        """Get order manager statistics.

        Returns:
            Dictionary with order stats.
        """
        total_orders = len(self.order_history) + len(self.pending_orders)

        # Count filled vs cancelled/rejected
        filled = sum(
            1 for order in self.order_history
            if order.get('final_status') == 'FILLED'
        )
        cancelled = sum(
            1 for order in self.order_history
            if order.get('final_status') in ('CANCELLED', 'EXPIRED', 'REJECTED')
        )

        return {
            'total_orders': total_orders,
            'pending_orders': len(self.pending_orders),
            'completed_orders': len(self.order_history),
            'filled_orders': filled,
            'cancelled_orders': cancelled,
            'fill_rate': filled / len(self.order_history) if self.order_history else 0,
        }
