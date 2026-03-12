"""Position tracker for active SL/TP enforcement.

Tracks open positions and evaluates stop loss, trailing stop, and
take profit (including multiple targets) on each price update.
Generates exit signals when conditions are met.
"""

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from trading_automata.config.bot_config import RiskConfig
from trading_automata.strategies.base import Signal


@dataclass
class TrackedPosition:
    """State for an active position being monitored."""
    symbol: str
    entry_price: Decimal
    quantity: Decimal
    remaining_quantity: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    highest_price: Decimal  # For trailing stop
    trailing_active: bool = False
    tp_targets_hit: list[int] = field(default_factory=list)  # Indices of targets already hit


class PositionTracker:
    """Monitors open positions and generates exit signals on SL/TP hits."""

    def __init__(self, risk: RiskConfig):
        self.risk = risk
        self.positions: dict[str, TrackedPosition] = {}
        self.logger = logging.getLogger(f"{__name__}.PositionTracker")

    def open_position(self, symbol: str, entry_price: Decimal, quantity: Decimal) -> None:
        """Register a new position for tracking."""
        sl = entry_price * (1 - Decimal(str(self.risk.stop_loss_pct / 100)))
        tp = entry_price * (1 + Decimal(str(self.risk.take_profit_pct / 100)))

        self.positions[symbol] = TrackedPosition(
            symbol=symbol,
            entry_price=entry_price,
            quantity=quantity,
            remaining_quantity=quantity,
            stop_loss=sl,
            take_profit=tp,
            highest_price=entry_price,
        )
        self.logger.info(
            f"Tracking {symbol}: entry={entry_price}, SL={sl:.2f}, TP={tp:.2f}, "
            f"trailing={'ON' if self.risk.trailing_stop else 'OFF'}"
        )

    def close_position(self, symbol: str) -> None:
        """Remove position from tracking."""
        self.positions.pop(symbol, None)

    def evaluate(self, symbol: str, current_price: Decimal) -> Optional[Signal]:
        """Evaluate a price update against tracked positions.

        Returns a sell Signal if SL or TP is hit, None otherwise.
        """
        pos = self.positions.get(symbol)
        if not pos or pos.remaining_quantity <= 0:
            return None

        # Update highest price for trailing stop
        if current_price > pos.highest_price:
            pos.highest_price = current_price

        # --- Trailing stop logic ---
        if self.risk.trailing_stop:
            profit_pct = float((current_price - pos.entry_price) / pos.entry_price * 100)
            activation = self.risk.trailing_activation_pct

            if not pos.trailing_active and profit_pct >= activation:
                pos.trailing_active = True
                self.logger.info(f"{symbol} trailing stop activated at {profit_pct:.1f}% profit")

            if pos.trailing_active:
                trailing_sl = pos.highest_price * (1 - Decimal(str(self.risk.trailing_stop_pct / 100)))
                if trailing_sl > pos.stop_loss:
                    pos.stop_loss = trailing_sl

        # --- Stop loss check ---
        if current_price <= pos.stop_loss:
            self.logger.info(
                f"{symbol} STOP LOSS hit: price={current_price}, SL={pos.stop_loss}"
            )
            qty = pos.remaining_quantity
            self.close_position(symbol)
            return Signal(
                symbol=symbol,
                action="sell",
                quantity=qty,
                confidence=1.0,
                metadata={"reason": "stop_loss", "trigger_price": float(pos.stop_loss)},
            )

        # --- Multiple take profit targets ---
        if self.risk.take_profit_targets:
            for i, target in enumerate(self.risk.take_profit_targets):
                if i in pos.tp_targets_hit:
                    continue
                tp_price = pos.entry_price * (1 + Decimal(str(target.pct / 100)))
                if current_price >= tp_price:
                    sell_qty = (pos.quantity * Decimal(str(target.quantity_pct))).quantize(Decimal("0.001"))
                    sell_qty = min(sell_qty, pos.remaining_quantity)
                    if sell_qty <= 0:
                        continue
                    pos.tp_targets_hit.append(i)
                    pos.remaining_quantity -= sell_qty
                    self.logger.info(
                        f"{symbol} TP target #{i+1} hit: +{target.pct}%, "
                        f"selling {sell_qty} ({target.quantity_pct*100:.0f}%)"
                    )
                    if pos.remaining_quantity <= 0:
                        self.close_position(symbol)
                    return Signal(
                        symbol=symbol,
                        action="sell",
                        quantity=sell_qty,
                        confidence=1.0,
                        metadata={
                            "reason": "take_profit",
                            "target_index": i,
                            "target_pct": target.pct,
                            "trigger_price": float(tp_price),
                        },
                    )
            return None

        # --- Single take profit ---
        if current_price >= pos.take_profit:
            self.logger.info(
                f"{symbol} TAKE PROFIT hit: price={current_price}, TP={pos.take_profit}"
            )
            qty = pos.remaining_quantity
            self.close_position(symbol)
            return Signal(
                symbol=symbol,
                action="sell",
                quantity=qty,
                confidence=1.0,
                metadata={"reason": "take_profit", "trigger_price": float(pos.take_profit)},
            )

        return None
