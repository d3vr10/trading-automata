"""Bot lifecycle management via Redis pub/sub."""

import asyncio
import json
import logging
import uuid
from datetime import date

import redis.asyncio as aioredis
from sqlalchemy import select, func

logger = logging.getLogger(__name__)

COMMANDS_CHANNEL = "engine:commands"
STATUS_HASH = "engine:status"


async def send_bot_command(
    redis_client: aioredis.Redis,
    action: str,
    bot_name: str,
    user_id: int,
) -> dict:
    """Send a command to the trading engine via Redis."""
    request_id = str(uuid.uuid4())
    command = {
        "action": action,
        "bot_name": bot_name,
        "user_id": user_id,
        "request_id": request_id,
    }
    await redis_client.publish(COMMANDS_CHANNEL, json.dumps(command))
    return {"request_id": request_id, "action": action, "bot_name": bot_name}


async def send_start_bot_command(
    redis_client: aioredis.Redis,
    bot_name: str,
    user_id: int,
    config: dict,
) -> dict:
    """Send a start_bot command with full config to the trading engine."""
    request_id = str(uuid.uuid4())
    command = {
        "action": "start_bot",
        "bot_name": bot_name,
        "user_id": user_id,
        "config": config,
        "request_id": request_id,
    }
    await redis_client.publish(COMMANDS_CHANNEL, json.dumps(command))
    return {"request_id": request_id, "action": "start_bot", "bot_name": bot_name}


EVENTS_CHANNEL = "engine:events"


async def send_command_and_wait(
    redis_client: aioredis.Redis,
    command: dict,
    timeout: float = 120.0,
) -> dict:
    """Send a command and wait for the response via Redis pub/sub."""
    request_id = command["request_id"]
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(EVENTS_CHANNEL)

    try:
        await redis_client.publish(COMMANDS_CHANNEL, json.dumps(command))
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=1.0,
            )
            if message and message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    if (data.get("event") == "command_response"
                            and data.get("data", {}).get("request_id") == request_id):
                        resp = data["data"]
                        if resp.get("success"):
                            return resp.get("data", {})
                        raise Exception(resp.get("error", "Command failed"))
                except json.JSONDecodeError:
                    continue
        raise TimeoutError("Engine did not respond in time")
    finally:
        await pubsub.unsubscribe(EVENTS_CHANNEL)
        await pubsub.close()


async def get_engine_health(redis_client: aioredis.Redis) -> dict:
    """Check if the trading engine is alive via its Redis heartbeat."""
    try:
        heartbeat = await redis_client.get("engine:heartbeat")
        return {
            "connected": heartbeat is not None,
            "status": "online" if heartbeat else "offline",
        }
    except Exception:
        return {"connected": False, "status": "offline"}


async def get_bot_statuses(
    redis_client: aioredis.Redis,
    user_id: int,
) -> dict:
    """Get all bot statuses for a user from Redis hash."""
    status_data = await redis_client.hgetall(STATUS_HASH)
    user_bots = {}
    prefix = f"bot:{user_id}:"
    for key, value in status_data.items():
        if key.startswith(prefix):
            bot_name = key[len(prefix):]
            user_bots[bot_name] = json.loads(value)
    return user_bots


async def get_account_snapshots(
    redis_client: aioredis.Redis,
    user_id: int,
) -> dict:
    """Get account snapshots for all bots belonging to a user.

    Returns per-bot account data + an aggregated total across all accounts.
    This is how platforms like 3Commas show portfolio value: per-account
    breakdown + unified total in display currency (USD).
    """
    # Scan for account snapshot keys for this user
    pattern = f"bot:{user_id}:*:account"
    accounts = []
    total_equity = 0.0
    total_cash = 0.0
    all_positions = []

    async for key in redis_client.scan_iter(match=pattern):
        raw = await redis_client.get(key)
        if not raw:
            continue
        snapshot = json.loads(raw)
        # Extract bot name from key: bot:{user_id}:{bot_name}:account
        parts = key.split(":")
        bot_name = ":".join(parts[2:-1])  # Handle bot names with colons
        snapshot["bot_name"] = bot_name
        accounts.append(snapshot)

        total_equity += snapshot.get("equity", 0)
        total_cash += snapshot.get("cash", 0)
        for pos in snapshot.get("positions", []):
            pos["bot_name"] = bot_name
            all_positions.append(pos)

    return {
        "total_equity": total_equity,
        "total_cash": total_cash,
        "currency": "USD",
        "accounts": accounts,
        "positions": all_positions,
    }


async def get_bot_events(
    redis_client: aioredis.Redis,
    user_id: int,
    bot_name: str,
    limit: int = 50,
) -> list:
    """Get recent events for a bot from Redis list."""
    key = f"bot:{user_id}:{bot_name}:events"
    raw_events = await redis_client.lrange(key, 0, limit - 1)
    return [json.loads(e) for e in raw_events]


async def persist_portfolio_snapshots(
    redis_client: aioredis.Redis,
    session_factory,
) -> int:
    """Scan all account snapshots from Redis and persist today's values to DB.

    Uses upsert (ON CONFLICT UPDATE) so running multiple times per day
    just updates the same row with the latest values.
    Returns number of snapshots persisted.
    """
    from app.models import PortfolioSnapshot, User

    today = date.today()
    count = 0

    # Scan all account snapshot keys: bot:{user_id}:{bot_name}:account
    async for key in redis_client.scan_iter(match="bot:*:account"):
        raw = await redis_client.get(key)
        if not raw:
            continue
        try:
            snapshot = json.loads(raw)
            parts = key.split(":")
            # key format: bot:{user_id}:{bot_name}:account
            user_id = int(parts[1])
            bot_name = ":".join(parts[2:-1])

            async with session_factory() as session:
                from sqlalchemy.dialects.postgresql import insert as pg_insert

                equity = snapshot.get("equity", 0)

                # Compute high-water mark from previous snapshots
                hwm_result = await session.execute(
                    select(func.max(PortfolioSnapshot.high_water_mark))
                    .where(
                        PortfolioSnapshot.user_id == user_id,
                        PortfolioSnapshot.bot_name == bot_name,
                    )
                )
                prev_hwm = float(hwm_result.scalar() or 0)
                hwm = max(prev_hwm, float(equity))
                drawdown_pct = ((hwm - float(equity)) / hwm * 100) if hwm > 0 else 0

                stmt = pg_insert(PortfolioSnapshot).values(
                    user_id=user_id,
                    bot_name=bot_name,
                    snapshot_date=today,
                    equity=equity,
                    cash=snapshot.get("cash", 0),
                    broker_type=snapshot.get("broker_type"),
                    currency=snapshot.get("currency", "USD"),
                    high_water_mark=hwm,
                    drawdown_pct=round(drawdown_pct, 4),
                ).on_conflict_do_update(
                    constraint="uq_portfolio_snapshot_daily",
                    set_={
                        "equity": equity,
                        "cash": snapshot.get("cash", 0),
                        "high_water_mark": hwm,
                        "drawdown_pct": round(drawdown_pct, 4),
                    },
                )
                await session.execute(stmt)
                await session.commit()
                count += 1
        except Exception as e:
            logger.debug(f"Failed to persist snapshot for key '{key}': {e}")

    return count


async def portfolio_snapshot_loop(
    redis_client: aioredis.Redis,
    session_factory,
    interval_seconds: int = 3600,
) -> None:
    """Background task: persist portfolio snapshots every hour."""
    try:
        while True:
            await asyncio.sleep(interval_seconds)
            try:
                count = await persist_portfolio_snapshots(redis_client, session_factory)
                if count:
                    logger.debug(f"Persisted {count} portfolio snapshot(s)")
            except Exception as e:
                logger.warning(f"Portfolio snapshot persistence failed: {e}")
    except asyncio.CancelledError:
        pass


async def get_portfolio_history(
    db,
    user_id: int,
    days: int = 90,
) -> list[dict]:
    """Get daily portfolio value history from DB snapshots.

    Returns aggregated total equity per day across all bots.
    """
    from sqlalchemy import func, cast, Date as SaDate
    from app.models import PortfolioSnapshot

    result = await db.execute(
        select(
            PortfolioSnapshot.snapshot_date,
            func.sum(PortfolioSnapshot.equity).label("total_equity"),
            func.sum(PortfolioSnapshot.cash).label("total_cash"),
        )
        .where(PortfolioSnapshot.user_id == user_id)
        .group_by(PortfolioSnapshot.snapshot_date)
        .order_by(PortfolioSnapshot.snapshot_date)
        .limit(days)
    )
    return [
        {
            "date": str(row.snapshot_date),
            "equity": float(row.total_equity or 0),
            "cash": float(row.total_cash or 0),
        }
        for row in result.all()
    ]
