"""
SAP ERP connection profiles management API routes.

Provides endpoints for dynamically connecting to SAP S/4HANA / ECC systems,
listing/saving connection profiles, testing credentials, and environment switching.
"""

import logging
import time
from uuid import uuid4
from datetime import datetime, timezone
from typing import Optional, List, Literal
from fastapi import APIRouter, Depends, Request, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.connectors.sap.client import SAPClient
from backend.connectors.sap.config import SAPConfig
from backend.connectors.sap.exceptions import SAPConnectorError
from backend.database.session import get_db, AsyncSessionLocal
from backend.database.models import SAPConnectionProfile
from backend.utils.crypto import encrypt_password, decrypt_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sap", tags=["SAP ERP Management"])


# ---------------------------------------------------------------------------
# Request and Response Schemas
# ---------------------------------------------------------------------------

class SAPProfileCreateRequest(BaseModel):
    """Request payload for creating a SAP connection profile."""

    name: str = Field(..., description="Profile display name")
    base_url: str = Field(..., description="SAP system base URL")
    auth_type: Literal["basic", "oauth2", "apikey"] = Field(default="basic")
    sap_client: str = Field(default="100", description="SAP Client number (Mandant)")
    username: Optional[str] = Field(default=None)
    password: Optional[str] = Field(default=None, description="Plaintext password (encrypted before storage)")
    api_key: Optional[str] = Field(default=None, description="Plaintext API key (encrypted before storage)")
    client_id: Optional[str] = Field(default=None)
    client_secret: Optional[str] = Field(default=None, description="Plaintext client secret (encrypted before storage)")
    token_url: Optional[str] = Field(default=None)


class SAPProfileResponse(BaseModel):
    """Single profile response (secrets are masked/hidden)."""

    id: str
    name: str
    base_url: str
    auth_type: str
    sap_client: str
    username: Optional[str] = None
    client_id: Optional[str] = None
    token_url: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SAPConnectRequest(BaseModel):
    """Request to connect to a saved SAP profile."""

    profile_id: str = Field(..., description="ID of saved profile to connect")


class SAPConnectResponse(BaseModel):
    """Response after a connect or test attempt."""

    status: str
    base_url: str
    message: str
    latency_ms: float = 0.0


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@router.get("/profiles", response_model=List[SAPProfileResponse])
async def list_sap_profiles(db: AsyncSession = Depends(get_db)):
    """Return all saved SAP connection profiles."""
    result = await db.execute(select(SAPConnectionProfile).order_by(SAPConnectionProfile.name))
    profiles = result.scalars().all()

    response_profiles = []
    for p in profiles:
        response_profiles.append(
            SAPProfileResponse(
                id=p.id,
                name=p.name,
                base_url=p.base_url,
                auth_type=p.auth_type,
                sap_client=p.sap_client,
                username=p.username,
                client_id=p.client_id,
                token_url=p.token_url,
                is_active=(p.is_active == "true"),
                created_at=p.created_at,
                updated_at=p.updated_at
            )
        )
    return response_profiles


@router.post("/profiles", response_model=SAPProfileResponse)
async def create_sap_profile(
    payload: SAPProfileCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Save a new SAP connection profile (secrets are encrypted)."""
    profile_id = str(uuid4())
    now = datetime.now(timezone.utc)

    new_profile = SAPConnectionProfile(
        id=profile_id,
        name=payload.name,
        base_url=payload.base_url,
        auth_type=payload.auth_type,
        sap_client=payload.sap_client,
        username=payload.username if payload.auth_type == "basic" else None,
        encrypted_password=encrypt_password(payload.password) if payload.password else None,
        encrypted_api_key=encrypt_password(payload.api_key) if payload.api_key else None,
        client_id=payload.client_id if payload.auth_type == "oauth2" else None,
        encrypted_client_secret=encrypt_password(payload.client_secret) if payload.client_secret else None,
        token_url=payload.token_url if payload.auth_type == "oauth2" else None,
        is_active="false",
        created_at=now,
        updated_at=now
    )

    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)

    return SAPProfileResponse(
        id=new_profile.id,
        name=new_profile.name,
        base_url=new_profile.base_url,
        auth_type=new_profile.auth_type,
        sap_client=new_profile.sap_client,
        username=new_profile.username,
        client_id=new_profile.client_id,
        token_url=new_profile.token_url,
        is_active=False,
        created_at=new_profile.created_at,
        updated_at=new_profile.updated_at
    )


@router.delete("/profiles/{profile_id}")
async def delete_sap_profile(profile_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a saved SAP connection profile (cannot delete active profile)."""
    result = await db.execute(
        select(SAPConnectionProfile).where(SAPConnectionProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="SAP profile not found")

    if profile.is_active == "true":
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the currently active SAP connection profile. Switch to another profile first."
        )

    await db.delete(profile)
    await db.commit()
    return {"message": "SAP profile successfully deleted", "id": profile_id}


@router.post("/test", response_model=SAPConnectResponse)
async def test_sap_connection(payload: SAPProfileCreateRequest):
    """Test SAP connection by performing a lightweight HTTP GET connection handshake.

    Verifies network reachability and authentication credentials.
    """
    from pydantic import SecretStr
    test_config = SAPConfig(
        _env_file=None,
        base_url=payload.base_url,
        auth_type=payload.auth_type,
        sap_client=payload.sap_client,
        username=payload.username,
        verify_ssl=False,
    )
    if payload.password:
        test_config.password = SecretStr(payload.password)
    if payload.api_key:
        test_config.api_key = SecretStr(payload.api_key)
    if payload.client_id:
        test_config.client_id = payload.client_id
    if payload.client_secret:
        test_config.client_secret = SecretStr(payload.client_secret)
    if payload.token_url:
        test_config.token_url = payload.token_url

    test_client = SAPClient(test_config)
    start_time = time.perf_counter()

    try:
        await test_client.connect()
        duration_ms = (time.perf_counter() - start_time) * 1000
        await test_client.disconnect()
        return SAPConnectResponse(
            status="connected",
            base_url=payload.base_url,
            latency_ms=round(duration_ms, 2),
            message="Successfully verified SAP HTTP handshake and authentication."
        )
    except Exception as e:
        logger.warning("SAP test connection failed to %s: %s", payload.base_url, e)
        return SAPConnectResponse(
            status="failed",
            base_url=payload.base_url,
            message=f"Connection failed: {str(e)}"
        )


@router.post("/connect", response_model=SAPConnectResponse)
async def connect_to_sap_server(
    payload: SAPConnectRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Connect to a saved SAP profile and rebind the active orchestrator SAP client.

    Disconnects old client, creates new SAPClient with decrypted credentials,
    verifies connectivity, and marks the profile as active in DB.
    """
    result = await db.execute(
        select(SAPConnectionProfile).where(SAPConnectionProfile.id == payload.profile_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="SAP profile not found")

    # Decrypt all stored secrets
    decrypted_pw = decrypt_password(profile.encrypted_password) if profile.encrypted_password else None
    decrypted_api_key = decrypt_password(profile.encrypted_api_key) if profile.encrypted_api_key else None
    decrypted_client_secret = decrypt_password(profile.encrypted_client_secret) if profile.encrypted_client_secret else None

    # Build SAPConfig from DB profile
    from pydantic import SecretStr
    new_config = SAPConfig(
        _env_file=None,
        base_url=profile.base_url,
        auth_type=profile.auth_type,
        sap_client=profile.sap_client,
        username=profile.username,
        verify_ssl=False,
    )
    if decrypted_pw:
        new_config.password = SecretStr(decrypted_pw)
    if decrypted_api_key:
        new_config.api_key = SecretStr(decrypted_api_key)
    if profile.client_id:
        new_config.client_id = profile.client_id
    if decrypted_client_secret:
        new_config.client_secret = SecretStr(decrypted_client_secret)
    if profile.token_url:
        new_config.token_url = profile.token_url

    new_client = SAPClient(new_config)

    # Verify connection works before rebinding
    try:
        await new_client.connect()
    except Exception as e:
        logger.error("Failed to connect to SAP profile %s (%s): %s", profile.name, profile.base_url, e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to connect to SAP server: {str(e)}"
        )

    # Disconnect old SAP client and rebind on orchestrator
    orchestrator = request.app.state.industrial_orchestrator
    if orchestrator.sap_client:
        try:
            await orchestrator.sap_client.disconnect()
        except Exception:
            pass  # Ignore disconnect errors for old client

    orchestrator.sap_client = new_client

    # Capture local variables BEFORE commit (prevent MissingGreenlet)
    target_base_url = profile.base_url
    target_profile_name = profile.name

    # Mark this profile active, deactivate all others
    await db.execute(
        update(SAPConnectionProfile)
        .where(SAPConnectionProfile.id != profile.id)
        .values(is_active="false", updated_at=datetime.now(timezone.utc))
    )
    profile.is_active = "true"
    profile.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return SAPConnectResponse(
        status="connected",
        base_url=target_base_url,
        message=f"Connected successfully to {target_profile_name}."
    )
