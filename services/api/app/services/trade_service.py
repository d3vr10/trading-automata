"""Trade and position query business logic."""

from datetime import datetime

from sqlalchemy import select, desc, func, case, cast, Date, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Trade, Position, PerformanceMetric, PortfolioSnapshot


async def list_trades(
    db: AsyncSession,
    user_id: int,
    symbol: str | None = None,
    strategy: str | None = None,
    bot_name: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Trade]:
    query = select(Trade).where(Trade.user_id == user_id)
    if symbol:
        query = query.where(Trade.symbol == symbol)
    if strategy:
        query = query.where(Trade.strategy == strategy)
    if bot_name:
        query = query.where(Trade.bot_name == bot_name)
    if date_from:
        query = query.where(Trade.entry_timestamp >= date_from)
    if date_to:
        query = query.where(Trade.entry_timestamp <= date_to)
    query = query.order_by(desc(Trade.entry_timestamp)).offset(offset).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def list_positions(
    db: AsyncSession,
    user_id: int,
    is_open: bool | None = True,
) -> list[Position]:
    query = select(Position).where(Position.user_id == user_id)
    if is_open is not None:
        query = query.where(Position.is_open == is_open)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_performance_metrics(
    db: AsyncSession,
    user_id: int,
    strategy: str | None = None,
    period: str | None = None,
    limit: int = 50,
) -> list[PerformanceMetric]:
    query = select(PerformanceMetric).where(PerformanceMetric.user_id == user_id)
    if strategy:
        query = query.where(PerformanceMetric.strategy == strategy)
    if period:
        query = query.where(PerformanceMetric.period == period)
    query = query.order_by(desc(PerformanceMetric.metric_date)).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_trade_summary(
    db: AsyncSession,
    user_id: int,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict:
    """Aggregate trade stats for dashboard."""
    where = [Trade.user_id == user_id]
    if date_from:
        where.append(Trade.entry_timestamp >= date_from)
    if date_to:
        where.append(Trade.entry_timestamp <= date_to)
    result = await db.execute(
        select(
            func.count(Trade.id).label("total_trades"),
            func.sum(Trade.net_pnl).label("total_pnl"),
            func.count(Trade.id).filter(Trade.is_winning_trade == True).label("winning_trades"),
        ).where(*where)
    )
    row = result.one()
    total = row.total_trades or 0
    winning = row.winning_trades or 0
    return {
        "total_trades": total,
        "total_pnl": float(row.total_pnl or 0),
        "winning_trades": winning,
        "win_rate": round(winning / total * 100, 1) if total > 0 else 0,
    }


async def get_portfolio_summary(db: AsyncSession, user_id: int) -> dict:
    """Portfolio overview: open positions value, unrealized P&L, allocation by symbol."""
    # Open positions summary
    pos_result = await db.execute(
        select(
            func.count(Position.id).label("open_count"),
            func.sum(Position.entry_price * Position.quantity).label("total_invested"),
            func.sum(Position.unrealized_pnl).label("total_unrealized_pnl"),
        )
        .where(Position.user_id == user_id, Position.is_open == True)
    )
    pos_row = pos_result.one()

    # Allocation breakdown by symbol
    alloc_result = await db.execute(
        select(
            Position.symbol,
            func.sum(Position.entry_price * Position.quantity).label("value"),
            func.sum(Position.unrealized_pnl).label("unrealized_pnl"),
            func.count(Position.id).label("count"),
        )
        .where(Position.user_id == user_id, Position.is_open == True)
        .group_by(Position.symbol)
        .order_by(desc("value"))
    )
    allocations = [
        {
            "symbol": row.symbol,
            "value": float(row.value or 0),
            "unrealized_pnl": float(row.unrealized_pnl or 0),
            "positions": row.count,
        }
        for row in alloc_result.all()
    ]

    # Strategy breakdown
    strat_result = await db.execute(
        select(
            Position.strategy,
            func.sum(Position.entry_price * Position.quantity).label("value"),
            func.count(Position.id).label("count"),
        )
        .where(Position.user_id == user_id, Position.is_open == True)
        .group_by(Position.strategy)
        .order_by(desc("value"))
    )
    by_strategy = [
        {"strategy": row.strategy, "value": float(row.value or 0), "positions": row.count}
        for row in strat_result.all()
    ]

    # Recent closed P&L (last 30 trades)
    recent_result = await db.execute(
        select(Trade.net_pnl)
        .where(Trade.user_id == user_id, Trade.exit_price.isnot(None))
        .order_by(desc(Trade.exit_timestamp))
        .limit(30)
    )
    recent_pnl = [float(row.net_pnl or 0) for row in recent_result.all()]

    return {
        "open_positions": pos_row.open_count or 0,
        "total_invested": float(pos_row.total_invested or 0),
        "total_unrealized_pnl": float(pos_row.total_unrealized_pnl or 0),
        "allocations": allocations,
        "by_strategy": by_strategy,
        "recent_pnl": list(reversed(recent_pnl)),  # chronological order
    }


async def get_equity_curve(
    db: AsyncSession,
    user_id: int,
    days: int = 90,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[dict]:
    """Daily cumulative P&L for equity curve chart.

    Returns list of {date, daily_pnl, cumulative_pnl} entries.
    """
    where = [Trade.user_id == user_id, Trade.exit_timestamp.isnot(None)]
    if date_from:
        where.append(Trade.exit_timestamp >= date_from)
    if date_to:
        where.append(Trade.exit_timestamp <= date_to)
    result = await db.execute(
        select(
            cast(Trade.exit_timestamp, Date).label("trade_date"),
            func.sum(Trade.net_pnl).label("daily_pnl"),
            func.count(Trade.id).label("trade_count"),
        )
        .where(*where)
        .group_by("trade_date")
        .order_by("trade_date")
        .limit(days)
    )
    rows = result.all()

    cumulative = 0.0
    curve = []
    for row in rows:
        daily = float(row.daily_pnl or 0)
        cumulative += daily
        curve.append({
            "date": str(row.trade_date),
            "daily_pnl": round(daily, 2),
            "cumulative_pnl": round(cumulative, 2),
            "trade_count": row.trade_count,
        })
    return curve


async def get_bot_stats(db: AsyncSession, user_id: int, bot_name: str) -> dict:
    """Aggregate trade stats for a specific bot."""
    result = await db.execute(
        select(
            func.count(Trade.id).label("total_trades"),
            func.sum(Trade.net_pnl).label("total_pnl"),
            func.count(case((Trade.is_winning_trade == True, 1))).label("winning_trades"),
            func.max(Trade.net_pnl).label("best_trade"),
            func.min(Trade.net_pnl).label("worst_trade"),
            func.avg(Trade.pnl_percent).label("avg_pnl_percent"),
        ).where(Trade.user_id == user_id, Trade.bot_name == bot_name)
    )
    row = result.one()
    total = row.total_trades or 0
    winning = row.winning_trades or 0
    return {
        "total_trades": total,
        "total_pnl": float(row.total_pnl or 0),
        "winning_trades": winning,
        "win_rate": round(winning / total * 100, 1) if total > 0 else 0,
        "best_trade": float(row.best_trade or 0),
        "worst_trade": float(row.worst_trade or 0),
        "avg_pnl_percent": round(float(row.avg_pnl_percent or 0), 2),
    }


async def get_bot_equity_curve(
    db: AsyncSession, user_id: int, bot_name: str, days: int = 90,
) -> list[dict]:
    """Daily cumulative P&L for a specific bot."""
    result = await db.execute(
        select(
            cast(Trade.exit_timestamp, Date).label("trade_date"),
            func.sum(Trade.net_pnl).label("daily_pnl"),
            func.count(Trade.id).label("trade_count"),
        )
        .where(
            Trade.user_id == user_id,
            Trade.bot_name == bot_name,
            Trade.exit_timestamp.isnot(None),
        )
        .group_by("trade_date")
        .order_by("trade_date")
        .limit(days)
    )
    rows = result.all()
    cumulative = 0.0
    curve = []
    for row in rows:
        daily = float(row.daily_pnl or 0)
        cumulative += daily
        curve.append({
            "date": str(row.trade_date),
            "daily_pnl": round(daily, 2),
            "cumulative_pnl": round(cumulative, 2),
            "trade_count": row.trade_count,
        })
    return curve


async def get_analytics(
    db: AsyncSession,
    user_id: int,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict:
    """Comprehensive analytics for the metrics page."""
    # Overall stats
    summary = await get_trade_summary(db, user_id, date_from=date_from, date_to=date_to)

    # Stats by strategy
    where = [Trade.user_id == user_id]
    if date_from:
        where.append(Trade.entry_timestamp >= date_from)
    if date_to:
        where.append(Trade.entry_timestamp <= date_to)
    strat_result = await db.execute(
        select(
            Trade.strategy,
            func.count(Trade.id).label("total_trades"),
            func.count(case((Trade.is_winning_trade == True, 1))).label("winning_trades"),
            func.sum(Trade.net_pnl).label("total_pnl"),
            func.avg(Trade.pnl_percent).label("avg_pnl_percent"),
            func.max(Trade.net_pnl).label("best_trade"),
            func.min(Trade.net_pnl).label("worst_trade"),
        )
        .where(*where)
        .group_by(Trade.strategy)
    )
    by_strategy = []
    for row in strat_result.all():
        total = row.total_trades or 0
        winning = row.winning_trades or 0
        losing = total - winning
        avg_win = avg_loss = 0.0
        # Profit factor approximation
        total_pnl = float(row.total_pnl or 0)
        by_strategy.append({
            "strategy": row.strategy,
            "total_trades": total,
            "winning_trades": winning,
            "losing_trades": losing,
            "win_rate": round(winning / total * 100, 1) if total > 0 else 0,
            "total_pnl": total_pnl,
            "avg_pnl_percent": round(float(row.avg_pnl_percent or 0), 2),
            "best_trade": float(row.best_trade or 0),
            "worst_trade": float(row.worst_trade or 0),
        })

    # Stats by symbol
    sym_result = await db.execute(
        select(
            Trade.symbol,
            func.count(Trade.id).label("total_trades"),
            func.count(case((Trade.is_winning_trade == True, 1))).label("winning_trades"),
            func.sum(Trade.net_pnl).label("total_pnl"),
        )
        .where(*where)
        .group_by(Trade.symbol)
        .order_by(desc("total_pnl"))
    )
    by_symbol = [
        {
            "symbol": row.symbol,
            "total_trades": row.total_trades,
            "win_rate": round((row.winning_trades or 0) / row.total_trades * 100, 1) if row.total_trades else 0,
            "total_pnl": float(row.total_pnl or 0),
        }
        for row in sym_result.all()
    ]

    # Equity curve
    equity_curve = await get_equity_curve(db, user_id, date_from=date_from, date_to=date_to)

    return {
        "summary": summary,
        "by_strategy": by_strategy,
        "by_symbol": by_symbol,
        "equity_curve": equity_curve,
    }


async def get_trade_duration_stats(
    db: AsyncSession,
    user_id: int,
    bot_name: str | None = None,
) -> list[dict]:
    """Average trade holding time per bot (closed trades only)."""
    where = [
        Trade.user_id == user_id,
        Trade.exit_timestamp.isnot(None),
    ]
    if bot_name:
        where.append(Trade.bot_name == bot_name)

    result = await db.execute(
        select(
            Trade.bot_name,
            func.avg(
                extract("epoch", Trade.exit_timestamp) - extract("epoch", Trade.entry_timestamp)
            ).label("avg_seconds"),
            func.count(Trade.id).label("trade_count"),
        )
        .where(*where)
        .group_by(Trade.bot_name)
    )
    return [
        {
            "bot_name": row.bot_name or "unknown",
            "avg_holding_seconds": round(float(row.avg_seconds or 0)),
            "trade_count": row.trade_count,
        }
        for row in result.all()
    ]


async def get_drawdown_stats(
    db: AsyncSession,
    user_id: int,
    bot_name: str | None = None,
) -> list[dict]:
    """Max and current drawdown per bot from portfolio snapshots."""
    where = [PortfolioSnapshot.user_id == user_id]
    if bot_name:
        where.append(PortfolioSnapshot.bot_name == bot_name)

    result = await db.execute(
        select(
            PortfolioSnapshot.bot_name,
            func.max(PortfolioSnapshot.drawdown_pct).label("max_drawdown_pct"),
            func.max(PortfolioSnapshot.high_water_mark).label("high_water_mark"),
        )
        .where(*where)
        .group_by(PortfolioSnapshot.bot_name)
    )

    stats = []
    for row in result.all():
        # Get current (latest) drawdown
        latest = await db.execute(
            select(PortfolioSnapshot.drawdown_pct, PortfolioSnapshot.equity)
            .where(
                PortfolioSnapshot.user_id == user_id,
                PortfolioSnapshot.bot_name == row.bot_name,
            )
            .order_by(desc(PortfolioSnapshot.snapshot_date))
            .limit(1)
        )
        latest_row = latest.first()
        stats.append({
            "bot_name": row.bot_name,
            "max_drawdown_pct": round(float(row.max_drawdown_pct or 0), 2),
            "current_drawdown_pct": round(float(latest_row.drawdown_pct if latest_row else 0), 2),
            "high_water_mark": float(row.high_water_mark or 0),
        })
    return stats


async def get_per_bot_portfolio_history(
    db: AsyncSession,
    user_id: int,
    days: int = 90,
) -> list[dict]:
    """Per-bot daily equity history (not aggregated)."""
    result = await db.execute(
        select(
            PortfolioSnapshot.snapshot_date,
            PortfolioSnapshot.bot_name,
            PortfolioSnapshot.equity,
        )
        .where(PortfolioSnapshot.user_id == user_id)
        .order_by(PortfolioSnapshot.snapshot_date)
        .limit(days * 20)  # generous limit for multiple bots
    )
    return [
        {
            "date": str(row.snapshot_date),
            "bot_name": row.bot_name,
            "equity": float(row.equity),
        }
        for row in result.all()
    ]
