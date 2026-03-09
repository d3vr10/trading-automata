"""JWT token creation and verification."""

from datetime import datetime, timedelta, UTC
from typing import Optional

from jose import JWTError, jwt

from app.config import settings


def create_access_token(user_id: int, role: str) -> str:
    """Create a short-lived access token."""
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: int) -> str:
    """Create a long-lived refresh token."""
    expire = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_token(token: str, expected_type: str = "access") -> Optional[dict]:
    """Verify and decode a JWT token.

    Returns:
        Decoded payload dict if valid, None if invalid.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != expected_type:
            return None
        return payload
    except JWTError:
        return None
