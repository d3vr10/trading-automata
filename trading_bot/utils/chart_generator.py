"""Chart generation utilities for trading bot metrics visualization."""

import io
import logging
from datetime import datetime
from typing import List, Dict, Any, Tuple
from decimal import Decimal

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
import numpy as np
import pandas as pd

from trading_bot.database.models import Trade

logger = logging.getLogger(__name__)


class ChartGenerator:
    """Generate charts for trading metrics."""

    # Chart styling
    FIGURE_SIZE = (12, 6)
    DPI = 100
    STYLE = "seaborn-v0_8-darkgrid"
    COLOR_PROFIT = "#26a69a"  # Green
    COLOR_LOSS = "#ef5350"    # Red
    COLOR_NEUTRAL = "#1f77b4"  # Blue

    @classmethod
    def generate_pnl_chart(cls, trades: List[Trade]) -> Tuple[bytes, Dict[str, Any]]:
        """Generate P&L cumulative chart.

        Args:
            trades: List of closed trades sorted by entry_timestamp

        Returns:
            Tuple of (image_bytes, metrics_dict)
        """
        if not trades:
            return None, {}

        # Sort trades by entry timestamp
        sorted_trades = sorted(trades, key=lambda t: t.entry_timestamp)

        # Calculate cumulative P&L
        timestamps = []
        cumulative_pnls = []
        cumulative = 0

        for trade in sorted_trades:
            if trade.gross_pnl is not None:
                cumulative += float(trade.gross_pnl)
                timestamps.append(trade.entry_timestamp)
                cumulative_pnls.append(cumulative)

        if not cumulative_pnls:
            return None, {}

        # Create figure
        fig, ax = plt.subplots(figsize=cls.FIGURE_SIZE, dpi=cls.DPI)
        fig.patch.set_facecolor("#f8f9fa")
        ax.set_facecolor("#f8f9fa")

        # Plot cumulative P&L
        ax.plot(
            timestamps,
            cumulative_pnls,
            linewidth=2.5,
            color=cls.COLOR_NEUTRAL,
            label="Cumulative P&L",
            marker="o",
            markersize=4,
        )

        # Fill area
        ax.fill_between(
            timestamps,
            cumulative_pnls,
            alpha=0.2,
            color=cls.COLOR_NEUTRAL,
        )

        # Highlight profit/loss regions
        for i, pnl in enumerate(cumulative_pnls):
            if pnl >= 0:
                ax.scatter(timestamps[i], pnl, color=cls.COLOR_PROFIT, s=30, zorder=5)
            else:
                ax.scatter(timestamps[i], pnl, color=cls.COLOR_LOSS, s=30, zorder=5)

        # Formatting
        ax.set_title("Cumulative P&L Over Time", fontsize=16, fontweight="bold", pad=20)
        ax.set_xlabel("Date", fontsize=11, fontweight="bold")
        ax.set_ylabel("P&L ($)", fontsize=11, fontweight="bold")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper left", fontsize=10)

        # Format x-axis dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.xticks(rotation=45, ha="right")

        # Format y-axis currency
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"${x:,.0f}"))

        # Add zero line
        ax.axhline(y=0, color="gray", linestyle="--", linewidth=1, alpha=0.5)

        # Calculate max drawdown
        running_max = np.maximum.accumulate(cumulative_pnls)
        drawdown = np.array(cumulative_pnls) - running_max
        max_drawdown = np.min(drawdown) if len(drawdown) > 0 else 0

        plt.tight_layout()

        # Save to bytes
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=cls.DPI, bbox_inches="tight", facecolor="#f8f9fa")
        buffer.seek(0)
        plt.close(fig)

        # Calculate metrics
        metrics = {
            "final_pnl": cumulative_pnls[-1],
            "max_drawdown": max_drawdown,
            "peak_pnl": np.max(cumulative_pnls),
            "total_trades": len(sorted_trades),
        }

        return buffer.getvalue(), metrics

    @classmethod
    def generate_performance_chart(
        cls,
        closed_trades: List[Trade],
        open_trades: List[Trade],
    ) -> bytes:
        """Generate performance summary chart with multiple subplots.

        Args:
            closed_trades: List of closed trades
            open_trades: List of open trades

        Returns:
            Image bytes
        """
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10), dpi=cls.DPI)
        fig.patch.set_facecolor("#f8f9fa")

        # 1. Win Rate Pie Chart
        if closed_trades:
            winning_trades = sum(1 for t in closed_trades if t.is_winning_trade)
            losing_trades = len(closed_trades) - winning_trades

            colors = [cls.COLOR_PROFIT, cls.COLOR_LOSS]
            sizes = [winning_trades, losing_trades]
            labels = [f"Wins\n({winning_trades})", f"Losses\n({losing_trades})"]

            ax1.pie(
                sizes,
                labels=labels,
                colors=colors,
                autopct="%1.0f%%",
                startangle=90,
                textprops={"fontsize": 10, "fontweight": "bold"},
            )
            ax1.set_title("Win Rate Distribution", fontsize=12, fontweight="bold", pad=15)
        else:
            ax1.text(0.5, 0.5, "No closed trades", ha="center", va="center", fontsize=11)
            ax1.set_title("Win Rate Distribution", fontsize=12, fontweight="bold", pad=15)
            ax1.axis("off")

        # 2. Key Metrics Table
        ax2.axis("off")
        metrics_text = cls._get_metrics_text(closed_trades, open_trades)
        ax2.text(
            0.05,
            0.95,
            metrics_text,
            transform=ax2.transAxes,
            fontsize=10,
            verticalalignment="top",
            family="monospace",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
        )

        # 3. Trade P&L Distribution (histogram)
        if closed_trades:
            pnls = [float(t.gross_pnl or 0) for t in closed_trades]
            ax3.hist(
                pnls,
                bins=max(10, len(closed_trades) // 3),
                color=cls.COLOR_NEUTRAL,
                alpha=0.7,
                edgecolor="black",
            )
            ax3.axvline(x=0, color="red", linestyle="--", linewidth=2, label="Break-even")
            ax3.set_title("Trade P&L Distribution", fontsize=12, fontweight="bold", pad=15)
            ax3.set_xlabel("P&L ($)", fontsize=10)
            ax3.set_ylabel("Frequency", fontsize=10)
            ax3.grid(True, alpha=0.3)
            ax3.legend()
        else:
            ax3.text(
                0.5, 0.5, "No closed trades", ha="center", va="center", fontsize=11
            )
            ax3.set_title("Trade P&L Distribution", fontsize=12, fontweight="bold", pad=15)
            ax3.axis("off")

        # 4. Strategy Performance
        if closed_trades:
            strategies = {}
            for trade in closed_trades:
                if trade.strategy not in strategies:
                    strategies[trade.strategy] = {"pnl": 0, "count": 0}
                strategies[trade.strategy]["pnl"] += float(trade.gross_pnl or 0)
                strategies[trade.strategy]["count"] += 1

            strat_names = list(strategies.keys())
            strat_pnls = [strategies[s]["pnl"] for s in strat_names]
            colors_strat = [cls.COLOR_PROFIT if p >= 0 else cls.COLOR_LOSS for p in strat_pnls]

            # Shorten strategy names for display
            display_names = [s.split("_")[0].upper() if len(s) > 10 else s for s in strat_names]

            ax4.barh(display_names, strat_pnls, color=colors_strat, alpha=0.8, edgecolor="black")
            ax4.axvline(x=0, color="black", linestyle="-", linewidth=1)
            ax4.set_title("Strategy Performance", fontsize=12, fontweight="bold", pad=15)
            ax4.set_xlabel("Total P&L ($)", fontsize=10)
            ax4.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"${x:,.0f}"))
            ax4.grid(True, alpha=0.3, axis="x")
        else:
            ax4.text(
                0.5, 0.5, "No closed trades", ha="center", va="center", fontsize=11
            )
            ax4.set_title("Strategy Performance", fontsize=12, fontweight="bold", pad=15)
            ax4.axis("off")

        plt.tight_layout()

        # Save to bytes
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=cls.DPI, bbox_inches="tight", facecolor="#f8f9fa")
        buffer.seek(0)
        plt.close(fig)

        return buffer.getvalue()

    @classmethod
    def _get_metrics_text(cls, closed_trades: List[Trade], open_trades: List[Trade]) -> str:
        """Generate metrics text for display.

        Args:
            closed_trades: List of closed trades
            open_trades: List of open trades

        Returns:
            Formatted metrics text
        """
        lines = ["📊 KEY METRICS"]
        lines.append("=" * 28)

        if closed_trades:
            total_trades = len(closed_trades)
            winning_trades = sum(1 for t in closed_trades if t.is_winning_trade)
            losing_trades = total_trades - winning_trades
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

            gross_profit = sum(
                float(t.gross_pnl or 0) for t in closed_trades if t.gross_pnl and float(t.gross_pnl) > 0
            )
            gross_loss = abs(
                sum(
                    float(t.gross_pnl or 0) for t in closed_trades if t.gross_pnl and float(t.gross_pnl) < 0
                )
            )
            profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0)
            total_pnl = gross_profit - gross_loss

            lines.append(f"Total Trades:    {total_trades}")
            lines.append(f"Wins/Losses:     {winning_trades}/{losing_trades}")
            lines.append(f"Win Rate:        {win_rate:.1f}%")
            lines.append(f"Profit Factor:   {profit_factor:.2f}" if profit_factor != float('inf') else f"Profit Factor:   ∞")
            lines.append("-" * 28)
            lines.append(f"Gross Profit:    ${gross_profit:>10,.0f}")
            lines.append(f"Gross Loss:      ${gross_loss:>10,.0f}")
            lines.append(f"Net P&L:         ${total_pnl:>10,.0f}")
        else:
            lines.append("No closed trades")

        lines.append("-" * 28)
        lines.append(f"Open Positions:  {len(open_trades)}")

        return "\n".join(lines)
