"""Virtual portfolio manager with fund compartmentalization (virtual fence).

Wraps the existing PortfolioManager to enforce per-bot capital allocation limits.
Ensures that each bot only spends up to its allocated capital, regardless of actual
account balance (the "virtual fence" concept).
"""

import logging
from decimal import Decimal
from typing import Optional

from trading_bot.brokers.base import IBroker
from trading_bot.config.bot_config import AllocationConfig, FenceConfig, RiskConfig
from trading_bot.data.models import Signal
from trading_bot.execution.order_manager import OrderManager
from trading_bot.portfolio.manager import PortfolioManager


logger = logging.getLogger(__name__)


class VirtualPortfolioManager:
    """Manages bot portfolio with virtual fund fence and risk controls.

    The virtual fence ensures that a bot never spends more capital than its allocation,
    creating a "sandbox" effect where the bot operates within its assigned budget.

    Hard fence (default): Strictly refuse any order that would exceed the virtual balance.
    Soft fence: Allow orders up to (allocated * (1 + overage_pct)), warn if overage is used.
    """

    def __init__(
        self,
        broker: IBroker,
        order_manager: OrderManager,
        allocation: AllocationConfig,
        fence: FenceConfig,
        risk: RiskConfig,
    ):
        """Initialize virtual portfolio manager.

        Args:
            broker: IBroker instance for account operations
            order_manager: OrderManager for order submission
            allocation: Fund allocation config (type, amount)
            fence: Fence config (type: hard/soft, overage_pct)
            risk: Risk config (stop_loss, take_profit, position sizes)
        """
        self.broker = broker
        self.order_manager = order_manager
        self.allocation = allocation
        self.fence = fence
        self.risk = risk

        # Virtual accounting - track capital allocated and spent (Decimal for precision)
        self.allocated_capital = Decimal(str(allocation.amount))
        self.virtual_spent = Decimal("0")  # Sum of buy order costs
        self.virtual_proceeds = Decimal("0")  # Sum of sell proceeds

        # Delegate real portfolio operations to existing PortfolioManager
        self._real_pm = PortfolioManager(
            broker=broker,
            order_manager=order_manager,
            max_position_size=Decimal(str(risk.max_position_size)),
            max_portfolio_risk=Decimal(str(risk.max_portfolio_risk)),
        )

        logger.info(
            f"Virtual portfolio initialized: "
            f"allocation={self.allocated_capital} {allocation.type}, "
            f"fence={fence.type}"
        )

    @property
    def virtual_balance(self) -> Decimal:
        """Get available virtual capital remaining.

        Returns:
            Decimal: capital available to this bot within the virtual fence
        """
        return self.allocated_capital - self.virtual_spent + self.virtual_proceeds

    def get_virtual_balance(self) -> Decimal:
        """Get available virtual capital. Alias for property."""
        return self.virtual_balance

    def can_execute_signal(self, signal: Signal) -> bool:
        """Check if signal can be executed within fence constraints.

        For sell signals: always return True (returning capital to the fence).
        For buy signals: check against virtual_balance based on fence type.

        Args:
            signal: Trading signal to validate

        Returns:
            bool: True if signal can be executed, False otherwise
        """
        # Sells always pass the fence check - they return capital
        if signal.action.lower() == 'sell':
            return self._real_pm.can_execute_signal(signal)

        # Buys: check against virtual balance
        if signal.action.lower() != 'buy':
            return False

        # First validate with real portfolio manager
        if not self._real_pm.can_execute_signal(signal):
            return False

        # Get current price for cost estimation
        current_price = self._real_pm._positions_cache.get(signal.symbol, {}).get('current_price')
        if not current_price:
            logger.warning(f"Cannot estimate cost for {signal.symbol} - no current price cached")
            return False

        # Estimate order cost
        qty = signal.quantity if signal.quantity else Decimal("1")
        estimated_cost = qty * Decimal(str(current_price))

        # Check fence constraints
        available = self.virtual_balance
        max_allowed = self.allocated_capital * Decimal(str(1 + self.fence.overage_pct / 100))

        if self.fence.type == 'hard':
            # Hard fence: no overage allowed
            if estimated_cost > available:
                logger.warning(
                    f"Buy signal rejected (hard fence): cost ${estimated_cost:.2f} "
                    f"exceeds virtual balance ${available:.2f}"
                )
                return False
        elif self.fence.type == 'soft':
            # Soft fence: allow overage up to configured percentage
            if estimated_cost > max_allowed:
                logger.warning(
                    f"Buy signal rejected (soft fence): cost ${estimated_cost:.2f} "
                    f"exceeds max allowed ${max_allowed:.2f}"
                )
                return False
            if estimated_cost > available:
                logger.warning(
                    f"Buy signal using overage: cost ${estimated_cost:.2f}, "
                    f"available ${available:.2f}, allowed ${max_allowed:.2f}"
                )

        return True

    def apply_risk_controls(self, signal: Signal, current_price: Decimal) -> Signal:
        """Inject risk management parameters into signal.

        Sets stop_loss and take_profit in signal.metadata based on configured
        percentages. These override any strategy-provided values.

        Args:
            signal: Trading signal to enrich
            current_price: Current asset price (Decimal)

        Returns:
            Signal: Updated signal with risk parameters in metadata
        """
        if not signal.metadata:
            signal.metadata = {}

        if signal.action.lower() == 'buy':
            # Stop loss: below entry price
            stop_loss = current_price * (1 - Decimal(str(self.risk.stop_loss_pct / 100)))
            signal.metadata['stop_loss'] = float(stop_loss)

            # Take profit: above entry price
            take_profit = current_price * (1 + Decimal(str(self.risk.take_profit_pct / 100)))
            signal.metadata['take_profit'] = float(take_profit)

        return signal

    def execute_signal_if_valid(self, signal: Signal) -> Optional[str]:
        """Execute signal if validation passes, tracking virtual balance.

        1. Validate signal with can_execute_signal()
        2. Apply risk controls (SL/TP)
        3. Adjust position size if needed
        4. Submit via order manager
        5. Update virtual_spent or virtual_proceeds on fill

        Args:
            signal: Trading signal to execute

        Returns:
            Optional[str]: Order ID if submitted, None if rejected
        """
        # Validate against fence
        if not self.can_execute_signal(signal):
            logger.info(f"Signal rejected by fence: {signal.symbol} {signal.action}")
            return None

        # Apply risk controls
        current_price = self._real_pm._positions_cache.get(signal.symbol, {}).get('current_price')
        if current_price:
            signal = self.apply_risk_controls(signal, Decimal(str(current_price)))
        else:
            logger.warning(f"No current price for {signal.symbol}, skipping risk controls")

        # Adjust position size based on virtual balance
        adjusted_qty = self.calculate_position_size(signal)
        if not adjusted_qty:
            logger.info(f"Position size adjusted to 0 for {signal.symbol}, rejecting signal")
            return None

        signal.quantity = adjusted_qty

        # Submit order
        order_id = self.order_manager.execute_signal(signal)
        if not order_id:
            logger.error(f"Failed to submit order for {signal.symbol}")
            return None

        # Update virtual accounting (simplified - real tracking happens on order fill in main.py)
        if signal.action.lower() == 'buy':
            estimated_cost = adjusted_qty * Decimal(str(current_price)) if current_price else Decimal("0")
            self.virtual_spent += estimated_cost
            logger.debug(f"Virtual spent updated: ${estimated_cost:.2f}, total: ${self.virtual_spent:.2f}")
        elif signal.action.lower() == 'sell':
            estimated_proceeds = adjusted_qty * Decimal(str(current_price)) if current_price else Decimal("0")
            self.virtual_proceeds += estimated_proceeds
            logger.debug(f"Virtual proceeds updated: ${estimated_proceeds:.2f}, total: ${self.virtual_proceeds:.2f}")

        return order_id

    def calculate_position_size(self, signal: Signal) -> Optional[Decimal]:
        """Calculate position size respecting virtual balance limits.

        Uses virtual_balance instead of real portfolio value to ensure positions
        stay within the bot's allocated capital.

        Args:
            signal: Trading signal with requested quantity

        Returns:
            Optional[Decimal]: Adjusted quantity, or None if invalid
        """
        if not signal.quantity:
            return None

        qty = Decimal(str(signal.quantity))
        max_position_pct = Decimal(str(self.risk.max_position_size))

        # Calculate maximum position size as percentage of virtual allocation
        max_position_value = self.allocated_capital * max_position_pct

        # Get current price
        current_price = self._real_pm._positions_cache.get(signal.symbol, {}).get('current_price')
        if not current_price:
            # If no price cached, return requested quantity (risky but handles edge case)
            logger.warning(f"No current price for {signal.symbol}, using requested quantity")
            return qty

        current_price = Decimal(str(current_price))

        # Check if requested size exceeds maximum
        position_value = qty * current_price
        if position_value > max_position_value:
            adjusted_qty = max_position_value / current_price
            logger.info(
                f"Position size adjusted from {qty} to {adjusted_qty:.4f} "
                f"for {signal.symbol} to stay within {self.risk.max_position_size*100:.0f}% limit"
            )
            return adjusted_qty

        return qty

    def refresh_state(self) -> None:
        """Refresh portfolio state from broker."""
        self._real_pm.refresh_state()

    def get_positions(self) -> list[dict]:
        """Get current positions from real portfolio manager."""
        return self._real_pm.get_positions()

    def get_portfolio_stats(self) -> dict:
        """Get portfolio statistics including virtual fence metrics.

        Returns:
            dict: Statistics including real and virtual portfolio info
        """
        stats = self._real_pm.get_portfolio_stats()

        # Add virtual fence information
        stats.update({
            'allocated_capital': float(self.allocated_capital),
            'virtual_balance': float(self.virtual_balance),
            'virtual_spent': float(self.virtual_spent),
            'virtual_proceeds': float(self.virtual_proceeds),
            'fence_type': self.fence.type,
            'fence_overage_pct': self.fence.overage_pct,
            'virtual_utilization_pct': float(
                (self.virtual_spent / self.allocated_capital * 100)
                if self.allocated_capital > 0
                else 0
            ),
        })

        return stats
