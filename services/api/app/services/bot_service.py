"""Bot lifecycle management via Redis pub/sub."""

import json
import uuid

import redis.asyncio as aioredis

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
