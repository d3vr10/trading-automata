"""Strategy catalog routes."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.services import strategy_service

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
    long_only: bool
    series: Optional[str] = None
    stats: StrategyStatsResponse


@router.get("/", response_model=list[StrategyResponse])
async def list_strategies(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List all available strategies with usage stats."""
    return await strategy_service.list_strategies(db, current_user.id)


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
