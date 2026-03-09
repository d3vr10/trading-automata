"""Redis event publisher for broadcasting trading engine events.

Publishes events to the 'engine:events' channel for consumption by
the API service (which forwards them to WebSocket clients).
"""

import json
import logging
from datetime import datetime, UTC
from typing import Any, Dict, Optional

import redis.asyncio as redis

from trading_automata.monitoring.logger import get_logger

logger = get_logger(__name__)

EVENTS_CHANNEL = "engine:events"
STATUS_HASH = "engine:status"


class EventPublisher:
    """Publishes trading engine events to Redis."""

    def __init__(self, redis_client: redis.Redis):
        self._redis = redis_client

    async def publish(self, event: str, data: Dict[str, Any],
                      user_id: Optional[int] = None,
                      bot_name: Optional[str] = None) -> None:
        """Publish an event to the events channel.

        Args:
            event: Event type (e.g., 'trade_executed', 'bot_status_changed')
            data: Event payload
            user_id: Owner user ID (for filtering on API side)
            bot_name: Bot that generated the event
        """
        message = {
            "event": event,
            "timestamp": datetime.now(UTC).isoformat(),
            "user_id": user_id,
            "bot_name": bot_name,
            "data": data,
        }
        try:
            await self._redis.publish(EVENTS_CHANNEL, json.dumps(message, default=str))
        except Exception as e:
            logger.warning(f"Failed to publish event '{event}': {e}")

    async def update_bot_status(self, bot_name: str, status: Dict[str, Any],
                                user_id: Optional[int] = None) -> None:
        """Update bot status in Redis hash (for polling by API).

        Args:
            bot_name: Bot identifier
            status: Status dict (running, paused, allocation, etc.)
            user_id: Owner user ID
        """
        key = f"bot:{user_id or 0}:{bot_name}"
        try:
            status["last_heartbeat"] = datetime.now(UTC).isoformat()
            await self._redis.hset(STATUS_HASH, key, json.dumps(status, default=str))
        except Exception as e:
            logger.warning(f"Failed to update bot status '{bot_name}': {e}")

    async def publish_trade_executed(self, bot_name: str, trade_data: Dict[str, Any],
                                     user_id: Optional[int] = None) -> None:
        await self.publish("trade_executed", trade_data, user_id, bot_name)

    async def publish_signal_generated(self, bot_name: str, signal_data: Dict[str, Any],
                                       user_id: Optional[int] = None) -> None:
        await self.publish("signal_generated", signal_data, user_id, bot_name)

    async def publish_bot_status_changed(self, bot_name: str, status: str,
                                         user_id: Optional[int] = None) -> None:
        await self.publish("bot_status_changed", {"status": status}, user_id, bot_name)

    async def publish_command_response(self, request_id: str, success: bool,
                                       data: Optional[Dict[str, Any]] = None,
                                       error: Optional[str] = None) -> None:
        """Publish response to a command request."""
        await self.publish("command_response", {
            "request_id": request_id,
            "success": success,
            "data": data,
            "error": error,
        })
