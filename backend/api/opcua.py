"""
OPC UA connection profiles and tag catalog management API routes.

Provides endpoints for dynamically connecting to servers, listing/saving
profiles, testing credentials, and re-indexing the local tag catalog.
"""

import logging
import time
from uuid import uuid4
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, BackgroundTasks, Depends, Request, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.connectors.opcua.connection import OPCUAClient
from backend.connectors.opcua.config import OPCUAConfig
from backend.connectors.opcua.crawler import OPCUATagCrawler
from backend.connectors.opcua.indexer import get_catalog_status
from backend.database.session import get_db, AsyncSessionLocal
from backend.database.models import OPCUAConnectionProfile
from backend.utils.crypto import encrypt_password, decrypt_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/opcua", tags=["OPC UA Management"])


# ---------------------------------------------------------------------------
# Request and Response Schemas
# ---------------------------------------------------------------------------

class OPCUAProfileCreateRequest(BaseModel):
    """Request payload for creating or updating a connection profile."""

    name: str = Field(..., description="Profile display name")
    endpoint_url: str = Field(..., description="OPC UA endpoint URL")
    auth_mode: str = Field(default="anonymous", description="'anonymous' or 'username_password'")
    username: Optional[str] = Field(default=None)
    password: Optional[str] = Field(default=None, description="Plaintext password (encrypted before storage)")
    security_policy: Optional[str] = Field(default=None, description="Optional security policy string")


class OPCUAProfileResponse(BaseModel):
    """Single profile response (passwords are masked)."""

    id: str
    name: str
    endpoint_url: str
    auth_mode: str
    username: Optional[str] = None
    security_policy: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OPCUAConnectRequest(BaseModel):
    """Request to connect to a saved profile or a specific endpoint."""

    profile_id: Optional[str] = Field(default=None, description="ID of saved profile to connect")
    endpoint_url: Optional[str] = Field(default=None, description="Direct endpoint (for test/one-off)")
    username: Optional[str] = None
    password: Optional[str] = None
    security_policy: Optional[str] = None


class OPCUAConnectResponse(BaseModel):
    """Response after a connect or test attempt."""

    status: str
    endpoint_url: str
    message: str
    latency_ms: float = 0.0
    tags_syncing: bool = False


# ---------------------------------------------------------------------------
# Helper Tasks
# ---------------------------------------------------------------------------

async def _run_reindex_task() -> None:
    """Background task: connect to current default OPC UA server, crawl, and index tags."""
    opcua_config = OPCUAConfig(_env_file=None)
    opcua_client = OPCUAClient(opcua_config)

    try:
        await opcua_client.connect()
        crawler = OPCUATagCrawler(opcua_client)

        async with AsyncSessionLocal() as db:
            count = await crawler.crawl_and_index(db)
            logger.info("OPC UA reindex background task completed: %d tags indexed.", count)
    except Exception as e:
        logger.error("OPC UA reindex background task failed: %s", e, exc_info=True)
    finally:
        await opcua_client.disconnect()


async def _reindex_with_client(client: OPCUAClient) -> None:
    """Background task to run tag catalog indexing using an existing active client."""
    try:
        crawler = OPCUATagCrawler(client)
        async with AsyncSessionLocal() as db:
            count = await crawler.crawl_and_index(db)
            logger.info("OPC UA dynamic reindex completed: %d tags indexed.", count)
    except Exception as e:
        logger.error("OPC UA dynamic reindex failed: %s", e, exc_info=True)


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@router.post("/reindex")
async def reindex_opcua_catalog(request: Request, background_tasks: BackgroundTasks):
    """Trigger an on-demand OPC UA address space crawl and catalog refresh.

    Uses the currently active client configured on the orchestrator.
    """
    logger.info("OPC UA catalog reindex triggered.")
    orchestrator = request.app.state.industrial_orchestrator
    
    if orchestrator.opcua_client:
        # Re-index using the dynamically bound active client
        background_tasks.add_task(_reindex_with_client, orchestrator.opcua_client)
    else:
        # Fallback to the environment configuration
        background_tasks.add_task(_run_reindex_task)

    return {
        "status": "sync_started",
        "message": "OPC UA catalog indexing started in background. Check /api/v1/opcua/status for progress.",
    }


@router.get("/status")
async def get_opcua_catalog_status(db: AsyncSession = Depends(get_db)):
    """Return the current OPC UA tag catalog status (tag count and last sync time)."""
    status = await get_catalog_status(db)
    return status


@router.get("/profiles", response_model=List[OPCUAProfileResponse])
async def list_profiles(db: AsyncSession = Depends(get_db)):
    """Return all saved OPC UA connection profiles."""
    result = await db.execute(select(OPCUAConnectionProfile).order_by(OPCUAConnectionProfile.name))
    profiles = result.scalars().all()
    
    response_profiles = []
    for p in profiles:
        response_profiles.append(
            OPCUAProfileResponse(
                id=p.id,
                name=p.name,
                endpoint_url=p.endpoint_url,
                auth_mode=p.auth_mode,
                username=p.username,
                security_policy=p.security_policy,
                is_active=(p.is_active == "true"),
                created_at=p.created_at,
                updated_at=p.updated_at
            )
        )
    return response_profiles


@router.post("/profiles", response_model=OPCUAProfileResponse)
async def create_profile(
    payload: OPCUAProfileCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Save a new OPC UA connection profile (password is encrypted)."""
    encrypted_pw = None
    if payload.password:
        encrypted_pw = encrypt_password(payload.password)

    profile_id = str(uuid4())
    now = datetime.now(timezone.utc)
    
    new_profile = OPCUAConnectionProfile(
        id=profile_id,
        name=payload.name,
        endpoint_url=payload.endpoint_url,
        auth_mode=payload.auth_mode,
        username=payload.username,
        encrypted_password=encrypted_pw,
        security_policy=payload.security_policy,
        is_active="false",
        created_at=now,
        updated_at=now
    )

    db.add(new_profile)
    await db.commit()
    await db.refresh(new_profile)

    return OPCUAProfileResponse(
        id=new_profile.id,
        name=new_profile.name,
        endpoint_url=new_profile.endpoint_url,
        auth_mode=new_profile.auth_mode,
        username=new_profile.username,
        security_policy=new_profile.security_policy,
        is_active=False,
        created_at=new_profile.created_at,
        updated_at=new_profile.updated_at
    )


@router.delete("/profiles/{profile_id}")
async def delete_profile(profile_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a saved connection profile (cannot delete active profile)."""
    result = await db.execute(
        select(OPCUAConnectionProfile).where(OPCUAConnectionProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
        
    if profile.is_active == "true":
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the currently active connection profile. Switch to another profile first."
        )

    await db.delete(profile)
    await db.commit()
    return {"message": "Profile successfully deleted", "id": profile_id}


@router.post("/test", response_model=OPCUAConnectResponse)
async def test_connection(payload: OPCUAConnectRequest):
    """Test connection credentials against an OPC UA server endpoint.
    
    Performs connection handshake and disconnects immediately.
    """
    url = payload.endpoint_url
    username = payload.username
    password = payload.password
    policy = payload.security_policy

    if payload.profile_id:
        # Load from DB instead
        async with AsyncSessionLocal() as db:
            res = await db.execute(
                select(OPCUAConnectionProfile).where(OPCUAConnectionProfile.id == payload.profile_id)
            )
            profile = res.scalar_one_or_none()
            if not profile:
                raise HTTPException(status_code=404, detail="Saved profile not found")
            url = profile.endpoint_url
            username = profile.username
            password = decrypt_password(profile.encrypted_password) if profile.encrypted_password else None
            policy = profile.security_policy

    if not url:
        raise HTTPException(status_code=400, detail="Endpoint URL must be specified")

    test_config = OPCUAConfig(
        endpoint_url=url,
        username=username,
        password=encrypt_password(password) if password else None,  # SecretStr internally expects password input
        security_string=policy
    )
    # Patch password configuration manually
    if username and password:
        from pydantic import SecretStr
        test_config.password = SecretStr(password)

    test_client = OPCUAClient(test_config)
    start_time = time.perf_counter()
    
    try:
        await test_client.connect()
        duration_ms = (time.perf_counter() - start_time) * 1000
        await test_client.disconnect()
        return OPCUAConnectResponse(
            status="connected",
            endpoint_url=url,
            latency_ms=round(duration_ms, 2),
            message="Successfully verified OPC UA handshake and connection."
        )
    except Exception as e:
        logger.warning("OPC UA test connection failed to %s: %s", url, e)
        return OPCUAConnectResponse(
            status="failed",
            endpoint_url=url,
            message=f"Connection failed: {str(e)}"
        )


@router.post("/connect", response_model=OPCUAConnectResponse)
async def connect_to_server(
    payload: OPCUAConnectRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Connect to a saved profile and rebind the active orchestrator client.

    Triggers a background catalog tag crawl after establishing connection.
    """
    if not payload.profile_id:
        raise HTTPException(status_code=400, detail="Profile ID must be specified")

    result = await db.execute(
        select(OPCUAConnectionProfile).where(OPCUAConnectionProfile.id == payload.profile_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    decrypted_pw = decrypt_password(profile.encrypted_password) if profile.encrypted_password else None

    # Step 1: Instantiate new config
    new_config = OPCUAConfig(
        endpoint_url=profile.endpoint_url,
        username=profile.username,
        security_string=profile.security_policy
    )
    if profile.username and decrypted_pw:
        from pydantic import SecretStr
        new_config.password = SecretStr(decrypted_pw)

    new_client = OPCUAClient(new_config)

    # Step 2: Establish connection to verify it works before rebinding
    try:
        await new_client.connect()
    except Exception as e:
        logger.error("Failed to connect to profile %s (%s): %s", profile.name, profile.endpoint_url, e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to connect to server: {str(e)}"
        )

    # Step 3: Rebind on active orchestrator in app state
    orchestrator = request.app.state.industrial_orchestrator
    if orchestrator.opcua_client:
        try:
            await orchestrator.opcua_client.disconnect()
        except Exception:
            pass # Ignore disconnect errors for old client

    orchestrator.opcua_client = new_client

    # Step 4: Update active profile status in DB
    target_endpoint_url = profile.endpoint_url
    target_profile_name = profile.name

    await db.execute(
        update(OPCUAConnectionProfile)
        .where(OPCUAConnectionProfile.id != profile.id)
        .values(is_active="false", updated_at=datetime.now(timezone.utc))
    )
    profile.is_active = "true"
    profile.updated_at = datetime.now(timezone.utc)
    await db.commit()

    # Step 5: Run background crawler to re-index the catalog
    background_tasks.add_task(_reindex_with_client, new_client)

    return OPCUAConnectResponse(
        status="connected",
        endpoint_url=target_endpoint_url,
        tags_syncing=True,
        message=f"Connected successfully to {target_profile_name}. Tag re-indexing started in the background."
    )
