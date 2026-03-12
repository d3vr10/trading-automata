"""Authentication routes: login, refresh, password reset."""

import logging
from datetime import datetime, timedelta, UTC
from typing import Annotated

import os

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status

logger = logging.getLogger(__name__)
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.metrics import auth_attempts_total, auth_token_refreshes_total
from app.auth.jwt import create_access_token, create_refresh_token, verify_token
from app.auth.password import hash_password, verify_password
from app.database import get_db
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Authenticate user and return JWT tokens."""
    client_ip = _get_client_ip(request)

    result = await db.execute(
        select(User).where(User.username == body.username)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        auth_attempts_total.labels(status="failure", client_ip=client_ip).inc()
        logger.warning("Login failed for username '%s' from %s", body.username, client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not user.is_active:
        auth_attempts_total.labels(status="failure", client_ip=client_ip).inc()
        logger.warning("Login attempt for disabled account '%s' from %s", body.username, client_ip)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    auth_attempts_total.labels(status="success", client_ip=client_ip).inc()
    logger.info("User '%s' logged in from %s", user.username, client_ip)

    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id)

    # Set refresh token as httponly cookie
    _set_refresh_cookie(response, refresh_token)

    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    refresh_token: Annotated[str, Cookie()] = "",
):
    """Get a new access token using a refresh token."""
    payload = verify_token(refresh_token, expected_type="refresh")
    if payload is None:
        auth_token_refreshes_total.labels(status="failure").inc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_id = int(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        auth_token_refreshes_total.labels(status="failure").inc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    auth_token_refreshes_total.labels(status="success").inc()

    access_token = create_access_token(user.id, user.role)
    new_refresh = create_refresh_token(user.id)

    _set_refresh_cookie(response, new_refresh)

    return TokenResponse(access_token=access_token)


def _set_refresh_cookie(response: Response, token: str) -> None:
    """Set the refresh token cookie, secure only in production."""
    is_prod = os.getenv("ENVIRONMENT", "development") == "production"
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=7 * 24 * 3600,  # 7 days
    )


@router.put("/password")
async def change_password(
    body: ChangePasswordRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Change own password (requires current password)."""
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    current_user.password_hash = hash_password(body.new_password)
    await db.commit()
    logger.info("User %d changed their password", current_user.id)
    return {"message": "Password changed successfully"}
