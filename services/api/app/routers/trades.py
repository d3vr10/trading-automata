"""Trade, position, and metrics query routes."""

import csv
import io
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.services import trade_service

router = APIRouter(prefix="/api", tags=["trading-data"])


class TradeResponse(BaseModel):
    id: int
    symbol: str
    strategy: str
    broker: str
    bot_name: Optional[str]
    entry_price: float
    entry_quantity: float
    entry_timestamp: Optional[datetime]
    exit_price: Optional[float]
    exit_timestamp: Optional[datetime]
    gross_pnl: Optional[float]
    net_pnl: Optional[float]
    pnl_percent: Optional[float]
    is_winning_trade: Optional[bool]

    model_config = {"from_attributes": True}


class PositionResponse(BaseModel):
    id: int
    symbol: str
    strategy: str
    broker: str
    bot_name: Optional[str]
    quantity: float
    entry_price: float
    current_price: Optional[float]
    is_open: bool
    unrealized_pnl: Optional[float]

    model_config = {"from_attributes": True}


class MetricResponse(BaseModel):
    id: int
    metric_date: str
    period: str
    strategy: str
    broker: str
    total_trades: int
    winning_trades: int
    win_rate: Optional[float]
    net_profit: float
    profit_factor: Optional[float]
    sharpe_ratio: Optional[float]
    portfolio_value: Optional[float]

    model_config = {"from_attributes": True}


class TradeSummaryResponse(BaseModel):
    total_trades: int
    total_pnl: float
    winning_trades: int
    win_rate: float


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


@router.get("/trades", response_model=list[TradeResponse])
async def list_trades(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    symbol: Optional[str] = None,
    strategy: Optional[str] = None,
    bot_name: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List trades for the current user (paginated, filterable)."""
    return await trade_service.list_trades(
        db, current_user.id,
        symbol=symbol, strategy=strategy, bot_name=bot_name,
        date_from=_parse_date(date_from), date_to=_parse_date(date_to),
        limit=limit, offset=offset,
    )


@router.get("/trades/export")
async def export_trades_csv(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    symbol: Optional[str] = None,
    strategy: Optional[str] = None,
    bot_name: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Export all matching trades as CSV."""
    trades = await trade_service.list_trades(
        db, current_user.id,
        symbol=symbol, strategy=strategy, bot_name=bot_name,
        date_from=_parse_date(date_from), date_to=_parse_date(date_to),
        limit=10000, offset=0,
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "ID", "Symbol", "Strategy", "Broker", "Bot", "Entry Price",
        "Entry Qty", "Entry Time", "Exit Price", "Exit Time",
        "Gross P&L", "Net P&L", "P&L %", "Win",
    ])
    for t in trades:
        writer.writerow([
            t.id, t.symbol, t.strategy, t.broker, t.bot_name,
            t.entry_price, t.entry_quantity, t.entry_timestamp,
            t.exit_price, t.exit_timestamp,
            t.gross_pnl, t.net_pnl, t.pnl_percent, t.is_winning_trade,
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=trades.csv"},
    )


@router.get("/positions", response_model=list[PositionResponse])
async def list_positions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    is_open: Optional[bool] = True,
):
    """List positions for the current user."""
    return await trade_service.list_positions(db, current_user.id, is_open=is_open)


@router.get("/metrics", response_model=list[MetricResponse])
async def list_metrics(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    strategy: Optional[str] = None,
    period: Optional[str] = None,
    limit: int = Query(default=50, le=200),
):
    """List performance metrics for the current user."""
    return await trade_service.get_performance_metrics(
        db, current_user.id, strategy=strategy, period=period, limit=limit,
    )


@router.get("/trades/summary", response_model=TradeSummaryResponse)
async def get_trade_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get aggregate trade statistics for the dashboard."""
    return await trade_service.get_trade_summary(db, current_user.id)


@router.get("/trades/duration-stats")
async def get_trade_duration_stats(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Average trade holding time per bot."""
    return await trade_service.get_trade_duration_stats(db, current_user.id)


@router.get("/portfolio/summary")
async def get_portfolio_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Portfolio overview: positions, allocation, unrealized P&L."""
    return await trade_service.get_portfolio_summary(db, current_user.id)


@router.get("/portfolio/equity-curve")
async def get_equity_curve(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=90, le=365),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Daily cumulative P&L time series for equity curve chart."""
    return await trade_service.get_equity_curve(
        db, current_user.id, days=days,
        date_from=_parse_date(date_from), date_to=_parse_date(date_to),
    )


@router.get("/analytics")
async def get_analytics(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Comprehensive analytics: by strategy, by symbol, equity curve."""
    return await trade_service.get_analytics(
        db, current_user.id,
        date_from=_parse_date(date_from), date_to=_parse_date(date_to),
    )
