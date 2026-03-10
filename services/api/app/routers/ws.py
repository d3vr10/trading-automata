"""WebSocket endpoint for real-time trading engine events.

Subscribes to Redis 'engine:events' channel and forwards events
to connected WebSocket clients, filtered by user_id.
"""

import asyncio
import json
import logging
from typing import Dict, Set

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import verify_token
from app.database import async_session
from app.metrics import ws_connections_active, ws_messages_forwarded_total
from app.models import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

EVENTS_CHANNEL = "engine:events"

# Active connections: user_id -> set of websockets
_connections: Dict[int, Set[WebSocket]] = {}


async def _authenticate_ws(token: str) -> User | None:
    """Verify JWT and return user, or None if invalid."""
    payload = verify_token(token, expected_type="access")
    if payload is None:
        return None
    user_id = int(payload["sub"])
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user and user.is_active:
            return user
    return None


@router.websocket("/api/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
):
    """WebSocket endpoint with JWT auth via query param.

    Clients connect with: ws://host/api/ws?token=<jwt>
    Receives real-time events from the trading engine, filtered by user ownership.
    """
    user = await _authenticate_ws(token)
    if user is None:
        await websocket.close(code=4001, reason="Authentication failed")
        return

    await websocket.accept()

    # Register connection
    if user.id not in _connections:
        _connections[user.id] = set()
    _connections[user.id].add(websocket)
    ws_connections_active.inc()
    logger.info(f"WebSocket connected: user={user.username} (total={sum(len(s) for s in _connections.values())})")

    try:
        # Keep alive — listen for client messages (ping/pong handled by protocol)
        while True:
            # We don't expect client messages, but we need to read to detect disconnects
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _connections[user.id].discard(websocket)
        if not _connections[user.id]:
            del _connections[user.id]
        ws_connections_active.dec()
        logger.info(f"WebSocket disconnected: user={user.username}")


async def broadcast_event(event_data: dict) -> None:
    """Send an event to all connected WebSocket clients for the target user."""
    user_id = event_data.get("user_id")

    targets: list[tuple[int, Set[WebSocket]]] = []
    if user_id is not None:
        conns = _connections.get(user_id)
        if conns:
            targets.append((user_id, conns))
    else:
        # Broadcast to all (e.g. system events)
        targets = list(_connections.items())

    message = json.dumps(event_data)
    for uid, conns in targets:
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            conns.discard(ws)


async def redis_event_listener(redis_client) -> None:
    """Subscribe to Redis events channel and forward to WebSocket clients.

    Runs as a background task during the API lifespan.
    """
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(EVENTS_CHANNEL)
    logger.info(f"Subscribed to Redis channel '{EVENTS_CHANNEL}' for WebSocket forwarding")

    try:
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=1.0,
            )
            if message and message["type"] == "message":
                try:
                    event_data = json.loads(message["data"])
                    event_type = event_data.get("event", "unknown")
                    ws_messages_forwarded_total.labels(event_type=event_type).inc()
                    await broadcast_event(event_data)
                except (json.JSONDecodeError, Exception) as e:
                    logger.warning(f"Failed to process Redis event: {e}")
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(EVENTS_CHANNEL)
        await pubsub.close()
        logger.info("Redis event listener stopped")
