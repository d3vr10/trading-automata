import logging
from typing import Dict, List, Optional, Any
from decimal import Decimal

from trading_bot.brokers.base import IBroker
from trading_bot.execution.order_manager import OrderManager
from trading_bot.strategies.base import Signal


logger = logging.getLogger(__name__)


class PortfolioManager:
    """Manages portfolio state and position management.

    Tracks positions, buying power, portfolio value, and validates
    whether signals can be executed given current constraints.
    """

    def __init__(
        self,
        broker: IBroker,
        order_manager: OrderManager,
        max_position_size: Decimal = Decimal('0.1'),
        max_portfolio_risk: Decimal = Decimal('0.02'),
    ):
        """Initialize portfolio manager.

        Args:
            broker: Broker instance
            order_manager: Order manager instance
            max_position_size: Max position as % of portfolio (default 10%)
            max_portfolio_risk: Max risk as % of portfolio (default 2%)
        """
        self.broker = broker
        self.order_manager = order_manager
        self.max_position_size = max_position_size
        self.max_portfolio_risk = max_portfolio_risk
        self._positions_cache = None
        self._account_cache = None

    def refresh_state(self) -> None:
        """Refresh portfolio state from broker.

        Should be called periodically to sync with broker state.
        """
        try:
            self._account_cache = self.broker.get_account()
            self._positions_cache = self.broker.get_positions()
            logger.debug("Portfolio state refreshed")
        except Exception as e:
            logger.error(f"Failed to refresh portfolio state: {e}")

    def get_account_info(self) -> Dict[str, Any]:
        """Get current account information.

        Returns:
            Account dictionary with portfolio value, buying power, etc.
        """
        if self._account_cache is None:
            self.refresh_state()
        return self._account_cache or {}

    def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions.

        Returns:
            List of position dictionaries.
        """
        if self._positions_cache is None:
            self.refresh_state()
        return self._positions_cache or []

    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get position for specific symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Position dictionary or None if not held.
        """
        positions = self.get_positions()
        for pos in positions:
            if pos['symbol'] == symbol:
                return pos
        return None

    def get_buying_power(self) -> Decimal:
        """Get available buying power.

        Returns:
            Buying power as Decimal.
        """
        account = self.get_account_info()
        return Decimal(str(account.get('buying_power', 0)))

    def get_portfolio_value(self) -> Decimal:
        """Get total portfolio value.

        Returns:
            Portfolio value as Decimal.
        """
        account = self.get_account_info()
        return Decimal(str(account.get('portfolio_value', 0)))

    def calculate_position_size(self, signal: Signal) -> Decimal:
        """Calculate appropriate position size for signal.

        Takes into account max position size constraints.

        Args:
            signal: Trading signal

        Returns:
            Recommended position size.
        """
        if signal.action == 'hold':
            return Decimal('0')

        if signal.quantity is None:
            return Decimal('0')

        portfolio_value = self.get_portfolio_value()
        if portfolio_value == 0:
            return signal.quantity

        # Don't let single position exceed max_position_size % of portfolio
        max_position_value = portfolio_value * self.max_position_size
        position_value = signal.quantity * signal.metadata.get('price', Decimal('1'))

        if position_value > max_position_value:
            # Scale down quantity
            adjusted_qty = (max_position_value / signal.metadata.get('price', Decimal('1')))
            logger.warning(
                f"Position size {signal.quantity} for {signal.symbol} exceeds "
                f"max {self.max_position_size * 100}% of portfolio. "
                f"Reducing to {adjusted_qty}"
            )
            return adjusted_qty

        return signal.quantity

    def can_execute_signal(self, signal: Signal) -> bool:
        """Check if signal can be executed given portfolio constraints.

        Args:
            signal: Trading signal to check

        Returns:
            True if signal can be executed, False otherwise.
        """
        if signal.action == 'hold':
            return False

        if signal.action == 'buy':
            buying_power = self.get_buying_power()
            # Estimate cost (assuming no slippage for now)
            estimated_cost = signal.quantity * signal.metadata.get('price', Decimal('1'))

            if estimated_cost > buying_power:
                logger.warning(
                    f"Insufficient buying power for {signal}: "
                    f"need {estimated_cost}, have {buying_power}"
                )
                return False

            return True

        elif signal.action == 'sell':
            position = self.get_position(signal.symbol)
            if position is None:
                logger.warning(f"No position to sell for {signal.symbol}")
                return False

            if Decimal(str(position['qty'])) < signal.quantity:
                logger.warning(
                    f"Insufficient position for sell: "
                    f"have {position['qty']}, want to sell {signal.quantity}"
                )
                return False

            return True

        return False

    def execute_signal_if_valid(self, signal: Signal) -> Optional[str]:
        """Execute signal if it passes validation.

        Args:
            signal: Trading signal

        Returns:
            Order ID if executed, None otherwise.
        """
        if not self.can_execute_signal(signal):
            logger.info(f"Signal validation failed: {signal}")
            return None

        # Adjust quantity if needed
        adjusted_qty = self.calculate_position_size(signal)
        if adjusted_qty != signal.quantity:
            signal.quantity = adjusted_qty

        # Execute the order
        order_id = self.order_manager.execute_signal(signal)
        return order_id

    def get_portfolio_stats(self) -> Dict[str, Any]:
        """Get portfolio statistics.

        Returns:
            Dictionary with portfolio stats.
        """
        account = self.get_account_info()
        positions = self.get_positions()

        return {
            'portfolio_value': account.get('portfolio_value', 0),
            'buying_power': account.get('buying_power', 0),
            'cash': account.get('cash', 0),
            'num_positions': len(positions),
            'max_position_size': float(self.max_position_size),
            'max_portfolio_risk': float(self.max_portfolio_risk),
        }
