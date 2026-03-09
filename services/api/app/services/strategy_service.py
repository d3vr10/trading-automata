"""Strategy catalog service — static metadata + dynamic stats from DB."""

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Trade, Position


# Static strategy catalog — single source of truth for strategy metadata.
# The trading engine registers these by class name; this catalog enriches
# them with human-readable info for the UI.

STRATEGY_CATALOG: list[dict] = [
    {
        "id": "mean_reversion",
        "class_name": "MeanReversionStrategy",
        "name": "Mean Reversion",
        "short_description": "Bollinger Band mean-reversion entries and exits.",
        "description": (
            "Buys when price falls below the lower Bollinger Band (oversold) "
            "and sells when price reverts to the upper band. Works best in "
            "range-bound, choppy markets with clear support/resistance."
        ),
        "category": "mean-reversion",
        "risk_level": "medium",
        "target_win_rate": 65.0,
        "recommended_timeframe": "H1–H4",
        "indicators": ["Bollinger Bands", "SMA(20)"],
        "asset_classes": ["stocks", "crypto", "forex"],
        "long_only": False,
    },
    {
        "id": "momentum",
        "class_name": "MomentumStrategy",
        "name": "Momentum",
        "short_description": "Simple momentum with lookback period.",
        "description": (
            "Enters long when recent returns are positive over a configurable "
            "lookback window, exits when momentum turns negative. A classic "
            "trend-following approach suited for trending markets."
        ),
        "category": "trend-following",
        "risk_level": "medium",
        "target_win_rate": 55.0,
        "recommended_timeframe": "H4–D1",
        "indicators": ["Price Momentum", "Rate of Change"],
        "asset_classes": ["stocks", "crypto", "forex"],
        "long_only": False,
    },
    {
        "id": "rsi_atr_trend",
        "class_name": "RSIATRTrendStrategy",
        "name": "RSI + ATR Trend",
        "short_description": "RSI oversold/overbought with ATR-based risk sizing.",
        "description": (
            "Combines RSI for entry timing, dual EMAs for trend confirmation, "
            "and ATR for dynamic stop-loss/take-profit levels. Asset-agnostic — "
            "works on stocks, forex, crypto, and commodities."
        ),
        "category": "trend-following",
        "risk_level": "medium",
        "target_win_rate": 60.0,
        "recommended_timeframe": "H1–D1",
        "indicators": ["RSI(14)", "EMA(9/21)", "ATR(14)", "Support/Resistance"],
        "asset_classes": ["stocks", "crypto", "forex", "commodities"],
        "long_only": False,
    },
    {
        "id": "sigma_fast",
        "class_name": "SigmaSeriesFastStrategy",
        "name": "Sigma Fast",
        "short_description": "High-frequency VWAP momentum with volume spikes.",
        "description": (
            "Monitors VWAP crossovers combined with dual EMA (8/21) trend "
            "confirmation, RSI(7) momentum zones, and volume spike detection "
            "(>2x 20-bar average). Designed for rapid entries and tight risk "
            "management with 0.5x ATR stops and 1.5x ATR targets."
        ),
        "category": "momentum",
        "risk_level": "high",
        "target_win_rate": 93.0,
        "recommended_timeframe": "M5–M15",
        "indicators": ["VWAP", "EMA(8/21)", "RSI(7)", "ATR(7)", "Volume"],
        "asset_classes": ["stocks", "crypto"],
        "long_only": False,
        "series": "sigma",
    },
    {
        "id": "sigma_alpha",
        "class_name": "SigmaSeriesAlphaStrategy",
        "name": "Sigma Alpha",
        "short_description": "Conservative mean-reversion for steady growth.",
        "description": (
            "Uses Bollinger Band squeeze detection with RSI divergence "
            "confirmation. Waits for low-volatility contractions then enters "
            "on the breakout with ATR-based risk sizing. Designed for "
            "consistent, lower-drawdown returns."
        ),
        "category": "mean-reversion",
        "risk_level": "low",
        "target_win_rate": 88.0,
        "recommended_timeframe": "H1–H4",
        "indicators": ["Bollinger Bands", "RSI(14)", "ATR(14)", "EMA(20/50)"],
        "asset_classes": ["stocks", "crypto", "forex"],
        "long_only": False,
        "series": "sigma",
    },
    {
        "id": "sigma_alpha_bull",
        "class_name": "SigmaSeriesAlphaBullStrategy",
        "name": "Sigma Alpha Bull",
        "short_description": "Long-only bull market trend following.",
        "description": (
            "Triple EMA stack (21/50/200) with ADX trend strength filter, "
            "RSI momentum zones, and MACD histogram confirmation. Enters only "
            "in confirmed bull markets and exits on trend deterioration. "
            "No short trades — purely long-only for maximum bull capture."
        ),
        "category": "trend-following",
        "risk_level": "medium",
        "target_win_rate": 96.0,
        "recommended_timeframe": "H4–D1",
        "indicators": ["EMA(21/50/200)", "ADX(14)", "RSI(10)", "MACD(12,26,9)", "ATR(14)"],
        "asset_classes": ["stocks", "crypto"],
        "long_only": True,
        "series": "sigma",
    },
]

# Lookup by class_name for quick access
_CATALOG_BY_CLASS = {s["class_name"]: s for s in STRATEGY_CATALOG}
_CATALOG_BY_ID = {s["id"]: s for s in STRATEGY_CATALOG}


async def list_strategies(db: AsyncSession, user_id: int | None = None) -> list[dict]:
    """Return full strategy catalog enriched with live stats from the DB.

    Stats per strategy:
    - active_bots: number of open positions grouped by strategy
    - total_trades: lifetime trade count
    - win_rate: actual win rate from closed trades
    - total_pnl: lifetime net P&L
    - popularity_rank: 1-based rank by total_trades (descending)
    """
    # Query trade stats grouped by strategy
    trade_stats_q = (
        select(
            Trade.strategy,
            func.count(Trade.id).label("total_trades"),
            func.count(case((Trade.is_winning_trade == True, 1))).label("winning_trades"),
            func.sum(Trade.net_pnl).label("total_pnl"),
        )
        .group_by(Trade.strategy)
    )
    if user_id is not None:
        trade_stats_q = trade_stats_q.where(Trade.user_id == user_id)
    trade_result = await db.execute(trade_stats_q)
    trade_stats = {row.strategy: row for row in trade_result.all()}

    # Query active position count per strategy
    pos_stats_q = (
        select(
            Position.strategy,
            func.count(Position.id).label("active_positions"),
        )
        .where(Position.is_open == True)
        .group_by(Position.strategy)
    )
    if user_id is not None:
        pos_stats_q = pos_stats_q.where(Position.user_id == user_id)
    pos_result = await db.execute(pos_stats_q)
    pos_stats = {row.strategy: row.active_positions for row in pos_result.all()}

    # Enrich catalog with stats
    enriched = []
    for entry in STRATEGY_CATALOG:
        item = {**entry}

        # Match by strategy column (could be class_name or strategy name)
        stats = trade_stats.get(entry["class_name"]) or trade_stats.get(entry["id"]) or trade_stats.get(entry["name"])
        total = stats.total_trades if stats else 0
        winning = stats.winning_trades if stats else 0

        item["stats"] = {
            "total_trades": total,
            "winning_trades": winning,
            "win_rate": round(winning / total * 100, 1) if total > 0 else None,
            "total_pnl": float(stats.total_pnl or 0) if stats else 0.0,
            "active_positions": pos_stats.get(entry["class_name"], 0)
                + pos_stats.get(entry["id"], 0)
                + pos_stats.get(entry["name"], 0),
        }
        enriched.append(item)

    # Compute popularity rank (by total_trades descending)
    enriched.sort(key=lambda s: s["stats"]["total_trades"], reverse=True)
    for rank, item in enumerate(enriched, 1):
        item["stats"]["popularity_rank"] = rank

    # Re-sort by catalog order for stable output
    enriched.sort(key=lambda s: next(i for i, c in enumerate(STRATEGY_CATALOG) if c["id"] == s["id"]))

    return enriched


async def get_strategy(db: AsyncSession, strategy_id: str, user_id: int | None = None) -> dict | None:
    """Return a single strategy with stats, or None if not found."""
    if strategy_id not in _CATALOG_BY_ID:
        return None
    all_strategies = await list_strategies(db, user_id)
    return next((s for s in all_strategies if s["id"] == strategy_id), None)
