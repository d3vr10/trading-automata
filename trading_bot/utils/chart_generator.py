"""Chart generation utilities for trading bot metrics visualization."""

import asyncio
import io
import logging
import os
import sys
import time
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from trading_bot.database.models import Trade

logger = logging.getLogger(__name__)


def _get_system_info() -> Dict[str, Any]:
    """Get system resource information for diagnostics."""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return {
            "memory_mb": process.memory_info().rss / 1024 / 1024,
            "cpu_percent": process.cpu_percent(interval=0.1),
            "num_threads": process.num_threads(),
            "open_files": len(process.open_files()),
        }
    except ImportError:
        return {}
    except Exception as e:
        logger.debug(f"Failed to get system info: {e}")
        return {}


def _log_chart_diagnostic(stage: str, chart_type: str, data: Dict[str, Any]) -> None:
    """Log diagnostic information about chart generation."""
    sys_info = _get_system_info()
    log_msg = f"[{chart_type}] {stage}"
    if sys_info:
        log_msg += f" | Memory: {sys_info['memory_mb']:.1f}MB | Threads: {sys_info['num_threads']} | CPU: {sys_info['cpu_percent']:.1f}%"
    if data:
        log_msg += f" | {data}"
    logger.debug(log_msg)


class ChartGenerator:
    """Generate charts for trading metrics using Plotly."""

    # Color scheme
    COLOR_PROFIT = "#26a69a"  # Green
    COLOR_LOSS = "#ef5350"    # Red
    COLOR_NEUTRAL = "#1f77b4"  # Blue
    COLOR_BG = "#ffffff"
    COLOR_GRID = "#e0e0e0"

    # Plotly configuration
    TEMPLATE = "plotly_white"
    HEIGHT = 500
    WIDTH = 1000

    @classmethod
    def generate_pnl_chart(cls, trades: List[Trade]) -> Tuple[Optional[bytes], Dict[str, Any]]:
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

        # Log chart complexity
        _log_chart_diagnostic(
            "START",
            "PnL",
            {"trades": len(sorted_trades), "data_points": len(cumulative_pnls)}
        )

        try:
            # Create figure
            logger.debug("Creating Plotly figure for P&L chart")
            fig = go.Figure()

            # Add main cumulative P&L line
            logger.debug("Adding cumulative P&L trace")
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=cumulative_pnls,
                    mode="lines+markers",
                    name="Cumulative P&L",
                    line=dict(color=cls.COLOR_NEUTRAL, width=3),
                    marker=dict(size=6),
                    fill="tozeroy",
                    fillcolor=f"rgba({int('1f77b4'[1:3], 16)}, {int('1f77b4'[3:5], 16)}, {int('1f77b4'[5:7], 16)}, 0.15)",
                )
            )

            # Add zero line
            logger.debug("Adding zero line reference")
            fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)

            # Calculate max drawdown
            logger.debug("Calculating drawdown metrics")
            running_max = np.maximum.accumulate(cumulative_pnls)
            drawdown = np.array(cumulative_pnls) - running_max
            max_drawdown = float(np.min(drawdown)) if len(drawdown) > 0 else 0

            # Update layout
            logger.debug("Updating figure layout and styling")
            fig.update_layout(
                title={
                    "text": "Cumulative P&L Over Time",
                    "x": 0.5,
                    "xanchor": "center",
                    "font": {"size": 20, "color": "#000000"},
                },
                xaxis_title="Date",
                yaxis_title="P&L ($)",
                template=cls.TEMPLATE,
                height=cls.HEIGHT,
                width=cls.WIDTH,
                hovermode="x unified",
                margin=dict(l=80, r=40, t=80, b=60),
                font=dict(family="Arial, sans-serif", size=12),
                yaxis_tickformat="$,.0f",
                showlegend=True,
                legend=dict(x=0.02, y=0.98),
            )

            # Render to PNG bytes with timeout
            _log_chart_diagnostic("RENDER_START", "PnL", {})
            start_time = time.time()

            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                logger.debug("Creating new asyncio event loop")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            try:
                logger.debug("Starting Kaleido rendering (timeout: 15s)")
                png_bytes = loop.run_until_complete(
                    asyncio.wait_for(
                        asyncio.to_thread(
                            fig.to_image,
                            format="png",
                            width=cls.WIDTH,
                            height=cls.HEIGHT
                        ),
                        timeout=15.0  # 15 second timeout for P&L chart
                    )
                )
                elapsed = time.time() - start_time
                _log_chart_diagnostic(
                    "RENDER_SUCCESS",
                    "PnL",
                    {"size_kb": len(png_bytes) / 1024, "elapsed_s": f"{elapsed:.2f}"}
                )
            except asyncio.TimeoutError:
                elapsed = time.time() - start_time
                _log_chart_diagnostic(
                    "RENDER_TIMEOUT",
                    "PnL",
                    {"elapsed_s": f"{elapsed:.2f}", "timeout_s": 15}
                )
                logger.warning(
                    f"P&L chart rendering timed out after {elapsed:.1f}s. "
                    "This may indicate: Kaleido not installed, Chrome unavailable, "
                    "insufficient memory, or system resource constraints. "
                    "Install psutil for detailed diagnostics: pip install psutil"
                )
                return None, {}
            except Exception as e:
                elapsed = time.time() - start_time
                _log_chart_diagnostic(
                    "RENDER_ERROR",
                    "PnL",
                    {"error": str(e), "elapsed_s": f"{elapsed:.2f}"}
                )
                logger.error(
                    f"P&L chart rendering failed after {elapsed:.1f}s: {e}. "
                    "Check Kaleido installation: pip install -U kaleido. "
                    "Verify Chrome/Chromium is available on system."
                )
                return None, {}

        except Exception as e:
            logger.error(f"P&L chart generation failed: {e}", exc_info=True)
            return None, {}

        # Calculate metrics
        metrics = {
            "final_pnl": cumulative_pnls[-1],
            "max_drawdown": max_drawdown,
            "peak_pnl": float(np.max(cumulative_pnls)),
            "total_trades": len(sorted_trades),
        }

        return png_bytes, metrics

    @classmethod
    def generate_performance_chart(
        cls,
        closed_trades: List[Trade],
        open_trades: List[Trade],
    ) -> Optional[bytes]:
        """Generate performance summary chart with multiple subplots.

        Args:
            closed_trades: List of closed trades
            open_trades: List of open trades

        Returns:
            Image bytes or None if no data
        """
        if not closed_trades and not open_trades:
            return None

        # Create subplots
        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=(
                "Win Rate Distribution",
                "Key Metrics",
                "Trade P&L Distribution",
                "Strategy Performance",
            ),
            specs=[
                [{"type": "pie"}, {"type": "xy"}],
                [{"type": "histogram"}, {"type": "bar"}],
            ],
            vertical_spacing=0.15,
            horizontal_spacing=0.12,
        )

        # 1. Win Rate Pie Chart
        if closed_trades:
            winning_trades = sum(1 for t in closed_trades if t.is_winning_trade)
            losing_trades = len(closed_trades) - winning_trades

            fig.add_trace(
                go.Pie(
                    labels=["Wins", "Losses"],
                    values=[winning_trades, losing_trades],
                    marker=dict(colors=[cls.COLOR_PROFIT, cls.COLOR_LOSS]),
                    textposition="inside",
                    textinfo="label+percent",
                    hovertemplate="<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>",
                ),
                row=1,
                col=1,
            )
        else:
            fig.add_annotation(
                text="No closed trades",
                xref="x2 domain",
                yref="y2 domain",
                x=0.5,
                y=0.5,
                showarrow=False,
                font=dict(size=14, color="#999999"),
                row=1,
                col=1,
            )

        # 2. Key Metrics (as annotations table)
        metrics_text = cls._get_metrics_text(closed_trades, open_trades)
        fig.add_annotation(
            text=metrics_text,
            xref="x2",
            yref="y2",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(family="monospace", size=11, color="#000000"),
            bgcolor="rgba(240, 240, 240, 0.8)",
            bordercolor="#cccccc",
            borderwidth=1,
            borderpad=12,
            align="left",
            xanchor="center",
            yanchor="middle",
            row=1,
            col=2,
        )

        # 3. Trade P&L Distribution (histogram)
        if closed_trades:
            pnls = [float(t.gross_pnl or 0) for t in closed_trades]
            fig.add_trace(
                go.Histogram(
                    x=pnls,
                    nbinsx=max(10, len(closed_trades) // 3),
                    marker=dict(color=cls.COLOR_NEUTRAL, opacity=0.7),
                    hovertemplate="P&L Range: %{x}<br>Frequency: %{y}<extra></extra>",
                    name="",
                ),
                row=2,
                col=1,
            )

            # Add zero line
            fig.add_vline(x=0, line_dash="dash", line_color=cls.COLOR_LOSS, row=2, col=1)
        else:
            fig.add_annotation(
                text="No closed trades",
                xref="x3 domain",
                yref="y3 domain",
                x=0.5,
                y=0.5,
                showarrow=False,
                font=dict(size=14, color="#999999"),
                row=2,
                col=1,
            )

        # 4. Strategy Performance (bar chart)
        if closed_trades:
            strategies = {}
            for trade in closed_trades:
                if trade.strategy not in strategies:
                    strategies[trade.strategy] = {"pnl": 0, "count": 0}
                strategies[trade.strategy]["pnl"] += float(trade.gross_pnl or 0)
                strategies[trade.strategy]["count"] += 1

            strat_names = list(strategies.keys())
            strat_pnls = [strategies[s]["pnl"] for s in strat_names]
            colors_strat = [
                cls.COLOR_PROFIT if p >= 0 else cls.COLOR_LOSS for p in strat_pnls
            ]

            # Shorten strategy names for display
            display_names = [s.split("_")[0].upper() if len(s) > 10 else s for s in strat_names]

            fig.add_trace(
                go.Bar(
                    x=strat_pnls,
                    y=display_names,
                    orientation="h",
                    marker=dict(color=colors_strat),
                    text=[f"${p:,.0f}" for p in strat_pnls],
                    textposition="outside",
                    hovertemplate="<b>%{y}</b><br>P&L: $%{x:,.0f}<extra></extra>",
                    name="",
                ),
                row=2,
                col=2,
            )

            # Add zero line
            fig.add_vline(x=0, line_color="black", row=2, col=2)
        else:
            fig.add_annotation(
                text="No closed trades",
                xref="x4 domain",
                yref="y4 domain",
                x=0.5,
                y=0.5,
                showarrow=False,
                font=dict(size=14, color="#999999"),
                row=2,
                col=2,
            )

        # Update layout
        fig.update_layout(
            title={
                "text": "Trading Performance Summary",
                "x": 0.5,
                "xanchor": "center",
                "font": {"size": 22, "color": "#000000"},
            },
            template=cls.TEMPLATE,
            height=900,
            width=1400,
            showlegend=False,
            margin=dict(l=80, r=40, t=100, b=60),
            font=dict(family="Arial, sans-serif", size=11),
            hovermode="closest",
        )

        # Update axes
        fig.update_xaxes(title_text="P&L ($)", title_font=dict(size=12), row=2, col=1)
        fig.update_yaxes(title_text="Frequency", title_font=dict(size=12), row=2, col=1)
        fig.update_xaxes(title_text="Total P&L ($)", title_font=dict(size=12), row=2, col=2)

        # Hide axes for metrics subplot (1, 2) since it's text-only
        fig.update_xaxes(showgrid=False, zeroline=False, showline=False, showticklabels=False, row=1, col=2)
        fig.update_yaxes(showgrid=False, zeroline=False, showline=False, showticklabels=False, row=1, col=2)

        # Render to PNG bytes with timeout
        _log_chart_diagnostic(
            "RENDER_START",
            "Performance",
            {"closed": len(closed_trades), "open": len(open_trades)}
        )
        start_time = time.time()

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            logger.debug("Creating new asyncio event loop for performance chart")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            logger.debug("Starting Kaleido rendering for performance chart (timeout: 20s)")
            png_bytes = loop.run_until_complete(
                asyncio.wait_for(
                    asyncio.to_thread(
                        fig.to_image,
                        format="png",
                        width=1400,
                        height=900
                    ),
                    timeout=20.0  # 20 second timeout for complex performance chart
                )
            )
            elapsed = time.time() - start_time
            _log_chart_diagnostic(
                "RENDER_SUCCESS",
                "Performance",
                {"size_kb": len(png_bytes) / 1024, "elapsed_s": f"{elapsed:.2f}"}
            )
        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            _log_chart_diagnostic(
                "RENDER_TIMEOUT",
                "Performance",
                {"elapsed_s": f"{elapsed:.2f}", "timeout_s": 20}
            )
            logger.warning(
                f"Performance chart rendering timed out after {elapsed:.1f}s. "
                "Complex chart with {len(closed_trades)} trades may exceed system resources. "
                "Install psutil for detailed diagnostics: pip install psutil. "
                "Try reducing time range or filtering trades."
            )
            return None
        except Exception as e:
            elapsed = time.time() - start_time
            _log_chart_diagnostic(
                "RENDER_ERROR",
                "Performance",
                {"error": str(e), "elapsed_s": f"{elapsed:.2f}"}
            )
            logger.error(
                f"Performance chart rendering failed after {elapsed:.1f}s: {e}. "
                "Check Kaleido installation: pip install -U kaleido. "
                "Verify Chrome/Chromium is available on system.",
                exc_info=True
            )
            return None

        return png_bytes

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
                float(t.gross_pnl or 0)
                for t in closed_trades
                if t.gross_pnl and float(t.gross_pnl) > 0
            )
            gross_loss = abs(
                sum(
                    float(t.gross_pnl or 0)
                    for t in closed_trades
                    if t.gross_pnl and float(t.gross_pnl) < 0
                )
            )
            profit_factor = (
                (gross_profit / gross_loss)
                if gross_loss > 0
                else (float("inf") if gross_profit > 0 else 0)
            )
            total_pnl = gross_profit - gross_loss

            lines.append(f"Total Trades:    {total_trades}")
            lines.append(f"Wins/Losses:     {winning_trades}/{losing_trades}")
            lines.append(f"Win Rate:        {win_rate:.1f}%")
            if profit_factor != float("inf"):
                lines.append(f"Profit Factor:   {profit_factor:.2f}")
            else:
                lines.append(f"Profit Factor:   ∞")
            lines.append("-" * 28)
            lines.append(f"Gross Profit:    ${gross_profit:>10,.0f}")
            lines.append(f"Gross Loss:      ${gross_loss:>10,.0f}")
            lines.append(f"Net P&L:         ${total_pnl:>10,.0f}")
        else:
            lines.append("No closed trades")

        lines.append("-" * 28)
        lines.append(f"Open Positions:  {len(open_trades)}")

        return "\n".join(lines)
