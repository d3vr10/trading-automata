"""Broker credential management routes."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import BrokerCredential, User
from app.services.credential_service import encrypt_credential

router = APIRouter(prefix="/api/broker-credentials", tags=["broker-credentials"])


class CredentialResponse(BaseModel):
    id: int
    broker_type: str
    environment: str
    label: str
    api_key_masked: str  # Only show last 4 chars

    model_config = {"from_attributes": True}


class CreateCredentialRequest(BaseModel):
    broker_type: str  # alpaca, coinbase
    environment: str  # paper, live
    api_key: str
    secret_key: str
    passphrase: Optional[str] = None  # Coinbase only
    label: str


class UpdateCredentialRequest(BaseModel):
    api_key: Optional[str] = None
    secret_key: Optional[str] = None
    passphrase: Optional[str] = None
    label: Optional[str] = None


def _mask_key(key_ciphertext: str) -> str:
    """Return masked representation (not decrypting, just showing placeholder)."""
    return "****" + "****"


@router.get("/", response_model=list[CredentialResponse])
async def list_credentials(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List user's broker credentials (keys masked)."""
    result = await db.execute(
        select(BrokerCredential)
        .where(BrokerCredential.user_id == current_user.id)
        .order_by(BrokerCredential.id)
    )
    creds = result.scalars().all()
    return [
        CredentialResponse(
            id=c.id,
            broker_type=c.broker_type,
            environment=c.environment,
            label=c.label,
            api_key_masked=_mask_key(c.encrypted_api_key),
        )
        for c in creds
    ]


@router.post("/", response_model=CredentialResponse, status_code=status.HTTP_201_CREATED)
async def create_credential(
    body: CreateCredentialRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Store a new broker credential (encrypted at rest)."""
    cred = BrokerCredential(
        user_id=current_user.id,
        broker_type=body.broker_type,
        environment=body.environment,
        encrypted_api_key=encrypt_credential(body.api_key),
        encrypted_secret_key=encrypt_credential(body.secret_key),
        encrypted_passphrase=encrypt_credential(body.passphrase) if body.passphrase else None,
        label=body.label,
    )
    db.add(cred)
    await db.commit()
    await db.refresh(cred)
    return CredentialResponse(
        id=cred.id,
        broker_type=cred.broker_type,
        environment=cred.environment,
        label=cred.label,
        api_key_masked=_mask_key(cred.encrypted_api_key),
    )


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    credential_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete a broker credential."""
    result = await db.execute(
        select(BrokerCredential).where(
            BrokerCredential.id == credential_id,
            BrokerCredential.user_id == current_user.id,
        )
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")

    await db.delete(cred)
    await db.commit()
