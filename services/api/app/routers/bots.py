"""Bot management routes — CRUD + lifecycle via Redis commands."""

from typing import Annotated, Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import BotConfiguration, BrokerCredential, User
from app.services import bot_service, trade_service
from app.services.credential_service import decrypt_credential

router = APIRouter(prefix="/api/bots", tags=["bots"])


# ---- Schemas ----

class BotConfigResponse(BaseModel):
    id: int
    name: str
    strategy_id: str
    credential_id: int
    broker_type: str
    environment: str
    allocation: float
    fence_type: str
    fence_overage_pct: float
    stop_loss_pct: float
    take_profit_pct: float
    max_position_size: float
    poll_interval_minutes: int
    is_active: bool

    model_config = {"from_attributes": True}


class CreateBotRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    strategy_id: str
    credential_id: int
    allocation: float = Field(..., gt=0)
    fence_type: str = Field(default="hard")
    fence_overage_pct: float = Field(default=0.0, ge=0)
    stop_loss_pct: float = Field(default=2.0, gt=0)
    take_profit_pct: float = Field(default=6.0, gt=0)
    max_position_size: float = Field(default=0.1, gt=0)
    poll_interval_minutes: int = Field(default=1, ge=1)


class UpdateBotRequest(BaseModel):
    strategy_id: Optional[str] = None
    credential_id: Optional[int] = None
    allocation: Optional[float] = Field(default=None, gt=0)
    fence_type: Optional[str] = None
    fence_overage_pct: Optional[float] = Field(default=None, ge=0)
    stop_loss_pct: Optional[float] = Field(default=None, gt=0)
    take_profit_pct: Optional[float] = Field(default=None, gt=0)
    max_position_size: Optional[float] = Field(default=None, gt=0)
    poll_interval_minutes: Optional[int] = Field(default=None, ge=1)


class BotCommandResponse(BaseModel):
    bot_name: str
    action: str
    status: str


# ---- Dependencies ----

async def get_redis() -> aioredis.Redis:
    """Get Redis client. Injected via app.state in main.py."""
    raise NotImplementedError("Redis dependency not configured")


# ---- Helpers ----

def _to_response(bot: BotConfiguration, cred: BrokerCredential) -> BotConfigResponse:
    return BotConfigResponse(
        id=bot.id,
        name=bot.name,
        strategy_id=bot.strategy_id,
        credential_id=bot.credential_id,
        broker_type=cred.broker_type,
        environment=cred.environment,
        allocation=float(bot.allocation),
        fence_type=bot.fence_type,
        fence_overage_pct=bot.fence_overage_pct,
        stop_loss_pct=bot.stop_loss_pct,
        take_profit_pct=bot.take_profit_pct,
        max_position_size=bot.max_position_size,
        poll_interval_minutes=bot.poll_interval_minutes,
        is_active=bot.is_active,
    )


async def _get_bot_or_404(
    db: AsyncSession, bot_id: int, user_id: int,
) -> BotConfiguration:
    result = await db.execute(
        select(BotConfiguration).where(
            BotConfiguration.id == bot_id,
            BotConfiguration.user_id == user_id,
        )
    )
    bot = result.scalar_one_or_none()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    return bot


# ---- CRUD ----

@router.get("/", response_model=list[BotConfigResponse])
async def list_bots(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List all bot configurations for the current user."""
    result = await db.execute(
        select(BotConfiguration, BrokerCredential)
        .join(BrokerCredential, BotConfiguration.credential_id == BrokerCredential.id)
        .where(BotConfiguration.user_id == current_user.id)
        .order_by(BotConfiguration.id)
    )
    return [_to_response(bot, cred) for bot, cred in result.all()]


@router.post("/", response_model=BotConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_bot(
    body: CreateBotRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new bot configuration."""
    # Verify the credential belongs to this user
    cred_result = await db.execute(
        select(BrokerCredential).where(
            BrokerCredential.id == body.credential_id,
            BrokerCredential.user_id == current_user.id,
        )
    )
    cred = cred_result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=400, detail="Invalid credential")

    # Check unique name per user
    existing = await db.execute(
        select(BotConfiguration).where(
            BotConfiguration.user_id == current_user.id,
            BotConfiguration.name == body.name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Bot name already exists")

    bot = BotConfiguration(
        user_id=current_user.id,
        name=body.name,
        strategy_id=body.strategy_id,
        credential_id=body.credential_id,
        allocation=body.allocation,
        fence_type=body.fence_type,
        fence_overage_pct=body.fence_overage_pct,
        stop_loss_pct=body.stop_loss_pct,
        take_profit_pct=body.take_profit_pct,
        max_position_size=body.max_position_size,
        poll_interval_minutes=body.poll_interval_minutes,
    )
    db.add(bot)
    await db.commit()
    await db.refresh(bot)
    return _to_response(bot, cred)


@router.get("/{bot_id}", response_model=BotConfigResponse)
async def get_bot(
    bot_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get a specific bot configuration."""
    bot = await _get_bot_or_404(db, bot_id, current_user.id)
    cred_result = await db.execute(
        select(BrokerCredential).where(BrokerCredential.id == bot.credential_id)
    )
    cred = cred_result.scalar_one()
    return _to_response(bot, cred)


@router.put("/{bot_id}", response_model=BotConfigResponse)
async def update_bot(
    bot_id: int,
    body: UpdateBotRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update a bot configuration."""
    bot = await _get_bot_or_404(db, bot_id, current_user.id)

    update_data = body.model_dump(exclude_none=True)

    # If changing credential, verify ownership
    if "credential_id" in update_data:
        cred_result = await db.execute(
            select(BrokerCredential).where(
                BrokerCredential.id == update_data["credential_id"],
                BrokerCredential.user_id == current_user.id,
            )
        )
        if not cred_result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Invalid credential")

    for key, value in update_data.items():
        setattr(bot, key, value)

    await db.commit()
    await db.refresh(bot)

    cred_result = await db.execute(
        select(BrokerCredential).where(BrokerCredential.id == bot.credential_id)
    )
    cred = cred_result.scalar_one()
    return _to_response(bot, cred)


@router.delete("/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bot(
    bot_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Delete a bot configuration."""
    bot = await _get_bot_or_404(db, bot_id, current_user.id)
    # Clean up Redis status entry
    status_key = f"bot:{current_user.id}:{bot.name}"
    await redis_client.hdel("engine:status", status_key)
    events_key = f"bot:{current_user.id}:{bot.name}:events"
    await redis_client.delete(events_key)
    account_key = f"bot:{current_user.id}:{bot.name}:account"
    await redis_client.delete(account_key)
    await db.delete(bot)
    await db.commit()


# ---- Lifecycle commands (Redis) ----

@router.get("/portfolio/history")
async def get_portfolio_history(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = 90,
):
    """Get daily portfolio value history for charting."""
    return await bot_service.get_portfolio_history(db, current_user.id, days)


@router.get("/accounts")
async def get_account_snapshots(
    current_user: Annotated[User, Depends(get_current_user)],
    redis_client: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Get aggregated account data from all running bots.

    Returns per-bot account snapshots (equity, cash, positions with live
    prices) plus a unified total — similar to 3Commas portfolio view.
    """
    return await bot_service.get_account_snapshots(redis_client, current_user.id)


@router.get("/status/all")
async def get_all_bot_status(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Get runtime status of all bots from Redis, reconciled with DB state.

    If a bot is marked is_active=False in the DB but Redis still says
    running=True, we correct the stale Redis entry. This prevents ghost
    bots from appearing as running after failed starts or missed stop events.
    """
    statuses = await bot_service.get_bot_statuses(redis_client, current_user.id)

    # Cross-reference with DB to fix stale entries
    result = await db.execute(
        select(BotConfiguration.name, BotConfiguration.is_active)
        .where(BotConfiguration.user_id == current_user.id)
    )
    db_bots = {name: is_active for name, is_active in result.all()}

    for bot_name, status in list(statuses.items()):
        if bot_name not in db_bots:
            # Bot was deleted — clean up stale Redis entry
            key = f"bot:{current_user.id}:{bot_name}"
            await redis_client.hdel("engine:status", key)
            del statuses[bot_name]
        elif not db_bots[bot_name] and status.get("running"):
            # DB says inactive but Redis says running — stale entry
            status["running"] = False
            status["paused"] = False
            status["stale"] = True

    # Enrich with per-account broker connection health
    # A fresh account snapshot (TTL 5min) indicates the broker is reachable
    for bot_name, status in statuses.items():
        account_key = f"bot:{current_user.id}:{bot_name}:account"
        has_snapshot = await redis_client.exists(account_key)
        status["broker_connected"] = bool(has_snapshot) if status.get("running") else None

    return statuses


@router.get("/engine/health")
async def engine_health(
    current_user: Annotated[User, Depends(get_current_user)],
    redis_client: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Check if the trading engine is online."""
    return await bot_service.get_engine_health(redis_client)


@router.get("/{bot_id}/stats")
async def get_bot_stats(
    bot_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Get performance stats for a specific bot."""
    bot = await _get_bot_or_404(db, bot_id, current_user.id)
    stats = await trade_service.get_bot_stats(db, current_user.id, bot.name)
    equity_curve = await trade_service.get_bot_equity_curve(db, current_user.id, bot.name)

    # Merge live account data from Redis
    account_key = f"bot:{current_user.id}:{bot.name}:account"
    raw = await redis_client.get(account_key)
    if raw:
        import json
        snapshot = json.loads(raw)
        stats["equity"] = snapshot.get("equity")
        stats["cash"] = snapshot.get("cash")

    stats["equity_curve"] = equity_curve
    return stats


@router.get("/{bot_id}/events")
async def get_bot_events(
    bot_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[aioredis.Redis, Depends(get_redis)],
    limit: int = 50,
):
    """Get recent activity events for a bot."""
    bot = await _get_bot_or_404(db, bot_id, current_user.id)
    return await bot_service.get_bot_events(redis_client, current_user.id, bot.name, limit)


@router.post("/{bot_id}/start", response_model=BotCommandResponse)
async def start_bot(
    bot_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Start a bot — sends config to the trading engine via Redis."""
    bot = await _get_bot_or_404(db, bot_id, current_user.id)

    # Get credential for broker info
    cred_result = await db.execute(
        select(BrokerCredential).where(BrokerCredential.id == bot.credential_id)
    )
    cred = cred_result.scalar_one()

    await bot_service.send_start_bot_command(
        redis_client,
        bot_name=bot.name,
        user_id=current_user.id,
        config={
            "strategy_id": bot.strategy_id,
            "broker_type": cred.broker_type,
            "environment": cred.environment,
            "api_key": decrypt_credential(cred.encrypted_api_key),
            "secret_key": decrypt_credential(cred.encrypted_secret_key),
            "passphrase": decrypt_credential(cred.encrypted_passphrase) if cred.encrypted_passphrase else "",
            "allocation": float(bot.allocation),
            "fence_type": bot.fence_type,
            "fence_overage_pct": bot.fence_overage_pct,
            "stop_loss_pct": bot.stop_loss_pct,
            "take_profit_pct": bot.take_profit_pct,
            "max_position_size": bot.max_position_size,
            "poll_interval_minutes": bot.poll_interval_minutes,
        },
    )

    # Mark as active in DB
    bot.is_active = True
    await db.commit()

    return BotCommandResponse(bot_name=bot.name, action="start", status="command_sent")


@router.post("/{bot_id}/pause", response_model=BotCommandResponse)
async def pause_bot(
    bot_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Pause a running bot."""
    bot = await _get_bot_or_404(db, bot_id, current_user.id)
    await bot_service.send_bot_command(redis_client, "pause_bot", bot.name, current_user.id)
    return BotCommandResponse(bot_name=bot.name, action="pause", status="command_sent")


@router.post("/{bot_id}/resume", response_model=BotCommandResponse)
async def resume_bot(
    bot_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Resume a paused bot."""
    bot = await _get_bot_or_404(db, bot_id, current_user.id)
    await bot_service.send_bot_command(redis_client, "resume_bot", bot.name, current_user.id)
    return BotCommandResponse(bot_name=bot.name, action="resume", status="command_sent")


@router.post("/{bot_id}/stop", response_model=BotCommandResponse)
async def stop_bot(
    bot_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Stop a running bot."""
    bot = await _get_bot_or_404(db, bot_id, current_user.id)
    await bot_service.send_bot_command(redis_client, "stop_bot", bot.name, current_user.id)

    bot.is_active = False
    await db.commit()

    return BotCommandResponse(bot_name=bot.name, action="stop", status="command_sent")
