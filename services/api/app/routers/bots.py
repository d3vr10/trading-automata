"""Bot management routes — CRUD + lifecycle via Redis commands."""

import logging
from typing import Annotated, Optional

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Request

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import BotConfiguration, BrokerCredential, User
from app.services import bot_service, trade_service
from app.metrics import bot_commands_total
from app.services.audit_service import log_action
from app.services.credential_service import decrypt_credential

router = APIRouter(prefix="/api/bots", tags=["bots"])


# ---- Schemas ----

class TakeProfitTarget(BaseModel):
    pct: float = Field(..., gt=0)
    quantity_pct: float = Field(..., gt=0, le=1)


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
    trailing_stop: bool
    trailing_stop_pct: float
    trailing_activation_pct: float
    take_profit_targets: Optional[list[TakeProfitTarget]]
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
    trailing_stop: bool = False
    trailing_stop_pct: float = Field(default=1.5, gt=0)
    trailing_activation_pct: float = Field(default=1.0, ge=0)
    take_profit_targets: Optional[list[TakeProfitTarget]] = None


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
    trailing_stop: Optional[bool] = None
    trailing_stop_pct: Optional[float] = Field(default=None, gt=0)
    trailing_activation_pct: Optional[float] = Field(default=None, ge=0)
    take_profit_targets: Optional[list[TakeProfitTarget]] = None


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
    tp_targets = None
    if bot.take_profit_targets:
        tp_targets = [TakeProfitTarget(**t) for t in bot.take_profit_targets]
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
        trailing_stop=bot.trailing_stop,
        trailing_stop_pct=bot.trailing_stop_pct,
        trailing_activation_pct=bot.trailing_activation_pct,
        take_profit_targets=tp_targets,
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

    tp_targets = [t.model_dump() for t in body.take_profit_targets] if body.take_profit_targets else None
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
        trailing_stop=body.trailing_stop,
        trailing_stop_pct=body.trailing_stop_pct,
        trailing_activation_pct=body.trailing_activation_pct,
        take_profit_targets=tp_targets,
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


@router.post("/{bot_id}/clone", response_model=BotConfigResponse, status_code=status.HTTP_201_CREATED)
async def clone_bot(
    bot_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Clone a bot configuration with a unique name."""
    source = await _get_bot_or_404(db, bot_id, current_user.id)

    # Generate unique name
    base_name = f"{source.name}-copy"
    name = base_name
    counter = 1
    while True:
        existing = await db.execute(
            select(BotConfiguration).where(
                BotConfiguration.user_id == current_user.id,
                BotConfiguration.name == name,
            )
        )
        if not existing.scalar_one_or_none():
            break
        counter += 1
        name = f"{base_name}-{counter}"

    clone = BotConfiguration(
        user_id=current_user.id,
        name=name,
        strategy_id=source.strategy_id,
        credential_id=source.credential_id,
        allocation=source.allocation,
        fence_type=source.fence_type,
        fence_overage_pct=source.fence_overage_pct,
        stop_loss_pct=source.stop_loss_pct,
        take_profit_pct=source.take_profit_pct,
        max_position_size=source.max_position_size,
        poll_interval_minutes=source.poll_interval_minutes,
        trailing_stop=source.trailing_stop,
        trailing_stop_pct=source.trailing_stop_pct,
        trailing_activation_pct=source.trailing_activation_pct,
        take_profit_targets=source.take_profit_targets,
    )
    db.add(clone)
    await db.commit()
    await db.refresh(clone)
    cred_result = await db.execute(
        select(BrokerCredential).where(BrokerCredential.id == clone.credential_id)
    )
    cred = cred_result.scalar_one()
    return _to_response(clone, cred)


# ---- Recovery (internal use by engine) ----

class BotRecoveryItem(BaseModel):
    """Bot config for recovery on engine startup."""
    user_id: int
    bot_id: int
    bot_name: str
    desired_state: str  # 'running' or 'paused'
    strategy_id: str
    broker_type: str
    environment: str
    api_key: str
    secret_key: str
    passphrase: str
    allocation: float
    fence_type: str
    fence_overage_pct: float
    stop_loss_pct: float
    take_profit_pct: float
    max_position_size: float
    poll_interval_minutes: int
    trailing_stop: bool = False
    trailing_stop_pct: float = 1.5
    trailing_activation_pct: float = 1.0
    take_profit_targets: Optional[list[dict]] = None


@router.get("/recovery/pending", response_model=list[BotRecoveryItem])
async def get_recovery_pending(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get all bots that should be recovered on engine startup.

    Returns bots with desired_state IN ('running', 'paused') across all users.
    Internal endpoint used by the trading engine for startup recovery.
    No auth required — engine calls this at startup before handling user commands.
    """
    result = await db.execute(
        select(BotConfiguration, BrokerCredential)
        .join(BrokerCredential, BotConfiguration.credential_id == BrokerCredential.id)
        .where(BotConfiguration.desired_state.in_(["running", "paused"]))
        .order_by(BotConfiguration.user_id, BotConfiguration.id)
    )

    items = []
    for bot, cred in result.all():
        items.append(BotRecoveryItem(
            user_id=bot.user_id,
            bot_id=bot.id,
            bot_name=bot.name,
            desired_state=bot.desired_state,
            strategy_id=bot.strategy_id,
            broker_type=cred.broker_type,
            environment=cred.environment,
            api_key=decrypt_credential(cred.encrypted_api_key),
            secret_key=decrypt_credential(cred.encrypted_secret_key),
            passphrase=decrypt_credential(cred.encrypted_passphrase) if cred.encrypted_passphrase else "",
            allocation=float(bot.allocation),
            fence_type=bot.fence_type,
            fence_overage_pct=bot.fence_overage_pct,
            stop_loss_pct=bot.stop_loss_pct,
            take_profit_pct=bot.take_profit_pct,
            max_position_size=bot.max_position_size,
            poll_interval_minutes=bot.poll_interval_minutes,
            trailing_stop=bot.trailing_stop,
            trailing_stop_pct=bot.trailing_stop_pct,
            trailing_activation_pct=bot.trailing_activation_pct,
            take_profit_targets=bot.take_profit_targets,
        ))

    return items


# ---- Lifecycle commands (Redis) ----

@router.get("/portfolio/history")
async def get_portfolio_history(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = 90,
):
    """Get daily portfolio value history for charting."""
    return await bot_service.get_portfolio_history(db, current_user.id, days)


@router.get("/portfolio/history/by-bot")
async def get_per_bot_portfolio_history(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = 90,
):
    """Per-bot daily equity history for multi-line chart."""
    return await trade_service.get_per_bot_portfolio_history(db, current_user.id, days)


@router.get("/drawdown")
async def get_drawdown_stats(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Max and current drawdown per bot."""
    return await trade_service.get_drawdown_stats(db, current_user.id)


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

    # Add duration stats
    duration_stats = await trade_service.get_trade_duration_stats(db, current_user.id, bot_name=bot.name)
    if duration_stats:
        stats["avg_holding_time_seconds"] = duration_stats[0]["avg_holding_seconds"]

    # Add drawdown stats
    drawdown_stats = await trade_service.get_drawdown_stats(db, current_user.id, bot_name=bot.name)
    if drawdown_stats:
        stats["max_drawdown_pct"] = drawdown_stats[0]["max_drawdown_pct"]
        stats["current_drawdown_pct"] = drawdown_stats[0]["current_drawdown_pct"]

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


class BacktestRequest(BaseModel):
    strategy_id: str
    symbol: str
    days: int = Field(default=90, le=365)
    initial_capital: float = Field(default=10000)
    stop_loss_pct: float = Field(default=2.0)
    take_profit_pct: float = Field(default=6.0)
    trailing_stop: bool = False


@router.post("/backtest")
async def run_backtest(
    body: BacktestRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    redis_client: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Run a backtest via the trading engine."""
    import uuid
    request_id = str(uuid.uuid4())
    command = {
        "action": "run_backtest",
        "request_id": request_id,
        "user_id": current_user.id,
        "strategy_id": body.strategy_id,
        "symbol": body.symbol,
        "days": body.days,
        "initial_capital": body.initial_capital,
        "stop_loss_pct": body.stop_loss_pct,
        "take_profit_pct": body.take_profit_pct,
        "trailing_stop": body.trailing_stop,
    }
    try:
        result = await bot_service.send_command_and_wait(redis_client, command, timeout=120)
        return result
    except TimeoutError:
        raise HTTPException(504, "Backtest timed out")
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/{bot_id}/start", response_model=BotCommandResponse)
async def start_bot(
    bot_id: int,
    request: Request,
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

    logger.info(
        "User %d starting bot '%s' (id=%d, broker=%s/%s)",
        current_user.id, bot.name, bot.id, cred.broker_type, cred.environment,
    )
    try:
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
    except Exception as e:
        logger.error("Failed to send start command for bot '%s': %s", bot.name, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to send start command: {e}")

    bot_commands_total.labels(action="start", broker_type=cred.broker_type).inc()

    # Mark as active + desired_state in DB
    bot.is_active = True
    bot.desired_state = "running"
    await log_action(db, current_user.id, "start_bot", "bot", bot.id, bot.name, ip_address=request.client.host if request.client else None)
    await db.commit()
    logger.debug("Start command sent for bot '%s', desired_state='running'", bot.name)

    return BotCommandResponse(bot_name=bot.name, action="start", status="command_sent")


@router.post("/{bot_id}/pause", response_model=BotCommandResponse)
async def pause_bot(
    bot_id: int,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Pause a running bot."""
    bot = await _get_bot_or_404(db, bot_id, current_user.id)
    logger.info("User %d pausing bot '%s' (id=%d)", current_user.id, bot.name, bot.id)
    await bot_service.send_bot_command(redis_client, "pause_bot", bot.name, current_user.id)

    cred_result = await db.execute(select(BrokerCredential).where(BrokerCredential.id == bot.credential_id))
    bot_commands_total.labels(action="pause", broker_type=cred_result.scalar_one().broker_type).inc()

    bot.desired_state = "paused"
    await log_action(db, current_user.id, "pause_bot", "bot", bot.id, bot.name, ip_address=request.client.host if request.client else None)
    await db.commit()

    return BotCommandResponse(bot_name=bot.name, action="pause", status="command_sent")


@router.post("/{bot_id}/resume", response_model=BotCommandResponse)
async def resume_bot(
    bot_id: int,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Resume a paused bot."""
    bot = await _get_bot_or_404(db, bot_id, current_user.id)
    logger.info("User %d resuming bot '%s' (id=%d)", current_user.id, bot.name, bot.id)
    await bot_service.send_bot_command(redis_client, "resume_bot", bot.name, current_user.id)

    cred_result = await db.execute(select(BrokerCredential).where(BrokerCredential.id == bot.credential_id))
    bot_commands_total.labels(action="resume", broker_type=cred_result.scalar_one().broker_type).inc()

    bot.desired_state = "running"
    await log_action(db, current_user.id, "resume_bot", "bot", bot.id, bot.name, ip_address=request.client.host if request.client else None)
    await db.commit()

    return BotCommandResponse(bot_name=bot.name, action="resume", status="command_sent")


@router.post("/{bot_id}/stop", response_model=BotCommandResponse)
async def stop_bot(
    bot_id: int,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Stop a running bot."""
    bot = await _get_bot_or_404(db, bot_id, current_user.id)
    logger.info("User %d stopping bot '%s' (id=%d)", current_user.id, bot.name, bot.id)
    await bot_service.send_bot_command(redis_client, "stop_bot", bot.name, current_user.id)

    cred_result = await db.execute(select(BrokerCredential).where(BrokerCredential.id == bot.credential_id))
    bot_commands_total.labels(action="stop", broker_type=cred_result.scalar_one().broker_type).inc()

    bot.is_active = False
    bot.desired_state = "stopped"
    await log_action(db, current_user.id, "stop_bot", "bot", bot.id, bot.name, ip_address=request.client.host if request.client else None)
    await db.commit()

    return BotCommandResponse(bot_name=bot.name, action="stop", status="command_sent")
