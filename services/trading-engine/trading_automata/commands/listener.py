"""Redis command listener for receiving API service commands.

Subscribes to 'engine:commands' channel and dispatches commands
to the orchestrator (start/stop/pause/resume bots, get status).
"""

import asyncio
import json
import logging
from typing import Any, Callable, Coroutine, Dict, Optional

import redis.asyncio as redis

from trading_automata.monitoring.logger import get_logger
from trading_automata.commands.publisher import EventPublisher

logger = get_logger(__name__)

COMMANDS_CHANNEL = "engine:commands"


class CommandListener:
    """Listens for commands from the API service via Redis pub/sub."""

    def __init__(self, redis_client: redis.Redis, publisher: EventPublisher):
        self._redis = redis_client
        self._publisher = publisher
        self._handlers: Dict[str, Callable] = {}
        self._running = False

    def register_handler(self, command: str,
                         handler: Callable[..., Coroutine]) -> None:
        """Register an async handler for a command.

        Args:
            command: Command name (e.g., 'pause_bot', 'get_status')
            handler: Async function that handles the command
        """
        self._handlers[command] = handler
        logger.debug(f"Registered command handler: {command}")

    async def start(self) -> None:
        """Start listening for commands. Runs until stopped."""
        self._running = True
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(COMMANDS_CHANNEL)
        logger.info(f"Command listener subscribed to '{COMMANDS_CHANNEL}'")

        try:
            while self._running:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message and message["type"] == "message":
                    await self._handle_message(message["data"])
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logger.info("Command listener cancelled")
        except Exception as e:
            logger.error(f"Command listener error: {e}", exc_info=True)
        finally:
            await pubsub.unsubscribe(COMMANDS_CHANNEL)
            await pubsub.close()
            logger.info("Command listener stopped")

    def stop(self) -> None:
        """Signal the listener to stop."""
        self._running = False

    async def _handle_message(self, raw_data: bytes) -> None:
        """Parse and dispatch a command message."""
        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON command: {raw_data[:200]}")
            return

        action = data.get("action")
        request_id = data.get("request_id", "")

        if not action:
            logger.warning(f"Command missing 'action' field: {data}")
            return

        handler = self._handlers.get(action)
        if not handler:
            logger.warning(f"Unknown command: {action}")
            if request_id:
                await self._publisher.publish_command_response(
                    request_id, success=False,
                    error=f"Unknown command: {action}",
                )
            return

        logger.info(f"Handling command: {action} (request_id={request_id})")
        try:
            result = await handler(data)
            if request_id:
                await self._publisher.publish_command_response(
                    request_id, success=True, data=result,
                )
        except Exception as e:
            logger.error(f"Command '{action}' failed: {e}", exc_info=True)
            if request_id:
                await self._publisher.publish_command_response(
                    request_id, success=False, error=str(e),
                )
