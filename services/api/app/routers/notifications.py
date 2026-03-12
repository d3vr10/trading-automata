"""Notification preference endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.services import notification_service as ns

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class NotificationPrefs(BaseModel):
    notify_trade_executed: bool = True
    notify_bot_error: bool = True
    notify_bot_stopped: bool = True


class UpdatePref(BaseModel):
    key: str
    enabled: bool


@router.get("/preferences", response_model=NotificationPrefs)
async def get_preferences(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get notification preferences."""
    prefs = await ns.get_notification_prefs(db, current_user.id)
    return NotificationPrefs(**prefs)


@router.put("/preferences")
async def update_preference(
    body: UpdatePref,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update a notification preference."""
    valid_keys = {"notify_trade_executed", "notify_bot_error", "notify_bot_stopped"}
    if body.key not in valid_keys:
        from fastapi import HTTPException
        raise HTTPException(400, f"Invalid key. Must be one of: {valid_keys}")
    await ns.set_notification_pref(db, current_user.id, body.key, body.enabled)
    return {"ok": True}


@router.get("/status")
async def notification_status():
    """Check if SMTP is configured."""
    return {"smtp_configured": ns.is_configured()}
