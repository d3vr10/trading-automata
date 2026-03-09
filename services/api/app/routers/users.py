"""User management routes (admin/root only for creation/listing)."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role
from app.database import get_db
from app.models import User
from app.services import user_service

router = APIRouter(prefix="/api/users", tags=["users"])


class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str]
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


class CreateUserRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    role: str = "user"


class UpdateUserRequest(BaseModel):
    email: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[str] = None


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get current user profile."""
    return current_user


@router.get("/", response_model=list[UserResponse])
async def list_users(
    current_user: Annotated[User, Depends(require_role(["root", "admin"]))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List all users (admin/root only)."""
    return await user_service.list_users(db)


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    current_user: Annotated[User, Depends(require_role(["root", "admin"]))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new user (admin/root only)."""
    if body.role == "root":
        raise HTTPException(status_code=400, detail="Cannot create another root user")
    if body.role == "admin" and current_user.role != "root":
        raise HTTPException(status_code=403, detail="Only root can create admin users")

    existing = await user_service.get_user_by_username(db, body.username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    return await user_service.create_user(
        db, username=body.username, password=body.password,
        role=body.role, email=body.email,
    )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    body: UpdateUserRequest,
    current_user: Annotated[User, Depends(require_role(["root", "admin"]))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update a user (admin/root only)."""
    user = await user_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.role == "root" and current_user.role != "root":
        raise HTTPException(status_code=403, detail="Cannot modify root user")

    if body.role == "root":
        raise HTTPException(status_code=400, detail="Cannot assign root role")

    return await user_service.update_user(
        db, user,
        email=body.email if body.email is not None else ...,
        is_active=body.is_active,
        role=body.role,
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: Annotated[User, Depends(require_role(["root"]))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete a user (root only)."""
    user = await user_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == "root":
        raise HTTPException(status_code=400, detail="Cannot delete root user")

    await user_service.delete_user(db, user)
