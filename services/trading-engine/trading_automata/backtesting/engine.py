"""Backtesting engine — replay historical bars through strategies.

Simulates trading without real orders, tracking virtual portfolio,
SL/TP enforcement (including trailing), and generating performance metrics.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

from trading_automata.config.bot_config import RiskConfig
from trading_automata.data.models import Bar
from trading_automata.risk.position_tracker import PositionTracker
from trading_automata.strategies.base import BaseStrategy, Signal

logger = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    """A completed round-trip trade."""
    symbol: str
    entry_price: float
    exit_price: float
    quantity: float
    entry_time: datetime
    exit_time: datetime
    pnl: float
    pnl_pct: float
    exit_reason: str  # "strategy", "stop_loss", "take_profit"


@dataclass
class BacktestResult:
    """Final backtesting results."""
    strategy_name: str
    symbol: str
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    total_return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    best_trade_pct: float
    worst_trade_pct: float
    max_drawdown_pct: float
    sharpe_ratio: Optional[float]
    trades: list[BacktestTrade]
    equity_curve: list[dict]  # [{date, equity}]


@dataclass
class _OpenPosition:
    symbol: str
    entry_price: Decimal
    quantity: Decimal
    entry_time: datetime


class BacktestEngine:
    """Replays bars through a strategy and tracks simulated performance."""

    def __init__(
        self,
        strategy: BaseStrategy,
        risk: RiskConfig,
        initial_capital: float = 10000.0,
        position_size_pct: float = 0.1,
    ):
        self.strategy = strategy
        self.risk = risk
        self.initial_capital = Decimal(str(initial_capital))
        self.position_size_pct = Decimal(str(position_size_pct))
        self.tracker = PositionTracker(risk)

    def run(self, bars: list[Bar]) -> BacktestResult:
        """Run backtest over a series of bars."""
        if not bars:
            return self._empty_result()

        capital = self.initial_capital
        positions: dict[str, _OpenPosition] = {}
        trades: list[BacktestTrade] = []
        equity_curve: list[dict] = []
        peak_equity = capital
        max_drawdown = Decimal("0")
        daily_returns: list[float] = []
        prev_equity = float(capital)

        for bar in bars:
            current_price = bar.close

            # Evaluate SL/TP from position tracker
            exit_signal = self.tracker.evaluate(bar.symbol, current_price)
            if exit_signal and bar.symbol in positions:
                pos = positions.pop(bar.symbol)
                self.tracker.close_position(bar.symbol)
                sell_qty = min(exit_signal.quantity or pos.quantity, pos.quantity)
                pnl = (current_price - pos.entry_price) * sell_qty
                capital += current_price * sell_qty
                trades.append(BacktestTrade(
                    symbol=bar.symbol,
                    entry_price=float(pos.entry_price),
                    exit_price=float(current_price),
                    quantity=float(sell_qty),
                    entry_time=pos.entry_time,
                    exit_time=bar.timestamp,
                    pnl=float(pnl),
                    pnl_pct=float(pnl / (pos.entry_price * sell_qty) * 100),
                    exit_reason=exit_signal.metadata.get("reason", "sl_tp"),
                ))

            # Get strategy signal
            signal = self.strategy.on_bar(bar)

            if signal and signal.action.lower() == "buy" and bar.symbol not in positions:
                # Size the position
                alloc = capital * self.position_size_pct
                qty = (alloc / current_price).quantize(Decimal("0.001"))
                if qty > 0 and alloc <= capital:
                    capital -= current_price * qty
                    positions[bar.symbol] = _OpenPosition(
                        symbol=bar.symbol,
                        entry_price=current_price,
                        quantity=qty,
                        entry_time=bar.timestamp,
                    )
                    self.tracker.open_position(bar.symbol, current_price, qty)

            elif signal and signal.action.lower() == "sell" and bar.symbol in positions:
                pos = positions.pop(bar.symbol)
                self.tracker.close_position(bar.symbol)
                pnl = (current_price - pos.entry_price) * pos.quantity
                capital += current_price * pos.quantity
                trades.append(BacktestTrade(
                    symbol=bar.symbol,
                    entry_price=float(pos.entry_price),
                    exit_price=float(current_price),
                    quantity=float(pos.quantity),
                    entry_time=pos.entry_time,
                    exit_time=bar.timestamp,
                    pnl=float(pnl),
                    pnl_pct=float(pnl / (pos.entry_price * pos.quantity) * 100),
                    exit_reason="strategy",
                ))

            # Calculate equity (cash + open position value)
            open_value = sum(
                bar.close * p.quantity if p.symbol == bar.symbol else p.entry_price * p.quantity
                for p in positions.values()
            )
            equity = capital + open_value

            # Track drawdown
            if equity > peak_equity:
                peak_equity = equity
            dd = (peak_equity - equity) / peak_equity * 100 if peak_equity > 0 else Decimal("0")
            if dd > max_drawdown:
                max_drawdown = dd

            # Daily equity curve (sample every bar)
            equity_curve.append({
                "date": bar.timestamp.isoformat(),
                "equity": float(equity),
            })

            # Daily returns for Sharpe
            eq_float = float(equity)
            if prev_equity > 0:
                daily_returns.append((eq_float - prev_equity) / prev_equity)
            prev_equity = eq_float

        # Close any remaining positions at last bar price
        if bars and positions:
            last_bar = bars[-1]
            for sym, pos in list(positions.items()):
                pnl = (last_bar.close - pos.entry_price) * pos.quantity
                capital += last_bar.close * pos.quantity
                trades.append(BacktestTrade(
                    symbol=sym,
                    entry_price=float(pos.entry_price),
                    exit_price=float(last_bar.close),
                    quantity=float(pos.quantity),
                    entry_time=pos.entry_time,
                    exit_time=last_bar.timestamp,
                    pnl=float(pnl),
                    pnl_pct=float(pnl / (pos.entry_price * pos.quantity) * 100),
                    exit_reason="end_of_data",
                ))

        # Compute metrics
        final = float(capital)
        total_return = (final - float(self.initial_capital)) / float(self.initial_capital) * 100
        winning = [t for t in trades if t.pnl > 0]
        losing = [t for t in trades if t.pnl <= 0]

        # Sharpe ratio (annualized, assuming daily bars)
        sharpe = None
        if len(daily_returns) > 1:
            import statistics
            mean_r = statistics.mean(daily_returns)
            std_r = statistics.stdev(daily_returns)
            if std_r > 0:
                sharpe = round(mean_r / std_r * (252 ** 0.5), 2)

        return BacktestResult(
            strategy_name=self.strategy.name,
            symbol=bars[0].symbol if bars else "",
            start_date=bars[0].timestamp.isoformat() if bars else "",
            end_date=bars[-1].timestamp.isoformat() if bars else "",
            initial_capital=float(self.initial_capital),
            final_capital=final,
            total_return_pct=round(total_return, 2),
            total_trades=len(trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            win_rate=round(len(winning) / len(trades) * 100, 1) if trades else 0,
            best_trade_pct=round(max((t.pnl_pct for t in trades), default=0), 2),
            worst_trade_pct=round(min((t.pnl_pct for t in trades), default=0), 2),
            max_drawdown_pct=round(float(max_drawdown), 2),
            sharpe_ratio=sharpe,
            trades=trades,
            equity_curve=equity_curve,
        )

    def _empty_result(self) -> BacktestResult:
        return BacktestResult(
            strategy_name=self.strategy.name,
            symbol="",
            start_date="",
            end_date="",
            initial_capital=float(self.initial_capital),
            final_capital=float(self.initial_capital),
            total_return_pct=0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0,
            best_trade_pct=0,
            worst_trade_pct=0,
            max_drawdown_pct=0,
            sharpe_ratio=None,
            trades=[],
            equity_curve=[],
        )
