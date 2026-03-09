"""Bot management routes — lifecycle via Redis commands."""

from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.models import User
from app.services import bot_service

router = APIRouter(prefix="/api/bots", tags=["bots"])


class BotCommandResponse(BaseModel):
    bot_name: str
    action: str
    status: str


async def get_redis() -> aioredis.Redis:
    """Get Redis client. Injected via app.state in main.py."""
    raise NotImplementedError("Redis dependency not configured")


@router.post("/{bot_name}/pause", response_model=BotCommandResponse)
async def pause_bot(
    bot_name: str,
    current_user: Annotated[User, Depends(get_current_user)],
    redis_client: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Pause a running bot."""
    await bot_service.send_bot_command(redis_client, "pause_bot", bot_name, current_user.id)
    return BotCommandResponse(bot_name=bot_name, action="pause", status="command_sent")


@router.post("/{bot_name}/resume", response_model=BotCommandResponse)
async def resume_bot(
    bot_name: str,
    current_user: Annotated[User, Depends(get_current_user)],
    redis_client: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Resume a paused bot."""
    await bot_service.send_bot_command(redis_client, "resume_bot", bot_name, current_user.id)
    return BotCommandResponse(bot_name=bot_name, action="resume", status="command_sent")


@router.post("/{bot_name}/stop", response_model=BotCommandResponse)
async def stop_bot(
    bot_name: str,
    current_user: Annotated[User, Depends(get_current_user)],
    redis_client: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Stop a running bot."""
    await bot_service.send_bot_command(redis_client, "stop_bot", bot_name, current_user.id)
    return BotCommandResponse(bot_name=bot_name, action="stop", status="command_sent")


@router.get("/status")
async def get_all_bot_status(
    current_user: Annotated[User, Depends(get_current_user)],
    redis_client: Annotated[aioredis.Redis, Depends(get_redis)],
):
    """Get status of all bots from Redis status hash."""
    return await bot_service.get_bot_statuses(redis_client, current_user.id)
