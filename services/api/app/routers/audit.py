"""Audit log routes — read-only access to user action history."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.services.audit_service import get_audit_log

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/")
async def list_audit_entries(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
):
    """Get audit log entries for the current user."""
    return await get_audit_log(
        db, current_user.id,
        limit=limit, offset=offset,
        action=action, resource_type=resource_type,
    )
