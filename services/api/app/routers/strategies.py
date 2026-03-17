"""Strategy catalog routes."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.services import strategy_service
from app.services.trading_pairs_service import get_trading_pairs

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


class StrategyStatsResponse(BaseModel):
    total_trades: int
    winning_trades: int
    win_rate: Optional[float]
    total_pnl: float
    active_positions: int
    popularity_rank: int


class StrategyResponse(BaseModel):
    id: str
    class_name: str
    name: str
    short_description: str
    description: str
    category: str
    risk_level: str
    target_win_rate: float
    recommended_timeframe: str
    indicators: list[str]
    asset_classes: list[str]
    asset_optimization: str
    long_only: bool
    series: Optional[str] = None
    stats: StrategyStatsResponse


@router.get("/", response_model=list[StrategyResponse])
async def list_strategies(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    broker_type: Optional[str] = None,
):
    """List available strategies with usage stats.

    If broker_type is provided, only returns strategies compatible with
    that broker's asset class (e.g., coinbase → generic + crypto).
    """
    return await strategy_service.list_strategies(db, current_user.id, broker_type)


class TradingPairResponse(BaseModel):
    symbol: str
    name: str
    quote: str


@router.get("/trading-pairs/{broker_type}", response_model=list[TradingPairResponse])
async def list_trading_pairs(
    broker_type: str,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """List available trading pairs for a broker type."""
    pairs = get_trading_pairs(broker_type)
    if not pairs:
        raise HTTPException(status_code=404, detail=f"Unknown broker type: {broker_type}")
    return pairs


class BrokerInfoResponse(BaseModel):
    broker_type: str
    min_order_usd: float
    currency: str
    notes: str


BROKER_INFO: dict[str, BrokerInfoResponse] = {
    "coinbase": BrokerInfoResponse(
        broker_type="coinbase",
        min_order_usd=5.0,
        currency="USD",
        notes="All orders execute on the LIVE market. Coinbase does not offer paper trading.",
    ),
    "alpaca": BrokerInfoResponse(
        broker_type="alpaca",
        min_order_usd=1.0,
        currency="USD",
        notes="Paper trading available. Fractional shares supported for most stocks.",
    ),
}


@router.get("/broker-info/{broker_type}", response_model=BrokerInfoResponse)
async def get_broker_info(
    broker_type: str,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get broker constraints (min order size, notes)."""
    info = BROKER_INFO.get(broker_type)
    if not info:
        raise HTTPException(status_code=404, detail=f"Unknown broker type: {broker_type}")
    return info


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    strategy_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get a single strategy with detailed stats."""
    result = await strategy_service.get_strategy(db, strategy_id, current_user.id)
    if not result:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return result
