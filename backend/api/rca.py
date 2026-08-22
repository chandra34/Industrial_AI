"""
REST API endpoints for Root Cause Analysis (RCA) events and manual triggers.

Provides:
  - GET /api/v1/rca/events             (Zone 3: Recent Alarm & RCA feed)
  - GET /api/v1/rca/events/{event_id}  (Detailed diagnostic drawer)
  - POST /api/v1/rca/trigger           (Zone 2: Manual 'Run RCA' button on Card)
  - PATCH /api/v1/rca/events/{event_id}/status (Acknowledge / Resolve)
"""

import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import get_db
from backend.database.models import RCAEvent
from backend.analytics.rca_engine import rca_engine
from backend.api.auth import get_current_user, FirebaseUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rca", tags=["Root Cause Analysis"])


# Pydantic Schemas
class RCATriggerRequest(BaseModel):
    """Payload for manual 1-click RCA trigger from a Dashboard Machine Card."""
    node_id: str = Field(..., description="OPC UA Node ID")
    asset_name: str = Field(..., description="Machine/Asset Name (e.g. 'Pump 02')")
    alarm_type: str = Field(default="Manual Diagnostic Request", description="Reason or Alarm description")
    severity: str = Field(default="WARNING", description="'WARNING' or 'CRITICAL'")
    extra_context: Optional[str] = Field(default="", description="Optional telemetry readings context")


class RCAEventSummaryResponse(BaseModel):
    """Summary format for Zone 3 feed."""
    id: str
    asset_name: str
    node_id: str
    alarm_type: str
    severity: str
    root_cause: str
    confidence_score: int
    status: str
    created_at: datetime
    recommended_actions: List[str] = []


class RCAEventDetailResponse(RCAEventSummaryResponse):
    """Full detail format for diagnostic slide-out drawer."""
    telemetry_evidence: Optional[str] = None
    sap_evidence: Optional[str] = None
    sop_evidence: Optional[str] = None
    raw_llm_response: Optional[str] = None


@router.get("/events", response_model=List[RCAEventSummaryResponse])
async def list_rca_events(
    limit: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = Query(default=None, description="Filter by status: 'open', 'acknowledged', 'resolved'"),
    asset_name: Optional[str] = Query(default=None, description="Filter by asset name substring"),
    db: AsyncSession = Depends(get_db),
    current_user: FirebaseUser = Depends(get_current_user),
):
    """List recent Root Cause Analysis reports for Dashboard Zone 3."""
    stmt = select(RCAEvent).order_by(desc(RCAEvent.created_at)).limit(limit)

    if status:
        stmt = stmt.where(RCAEvent.status == status)
    if asset_name:
        stmt = stmt.where(RCAEvent.asset_name.ilike(f"%{asset_name}%"))

    result = await db.execute(stmt)
    records = result.scalars().all()

    items = []
    for r in records:
        try:
            actions = json.loads(r.recommended_actions_json) if r.recommended_actions_json else []
        except Exception:
            actions = []
        items.append(
            RCAEventSummaryResponse(
                id=r.id,
                asset_name=r.asset_name,
                node_id=r.node_id,
                alarm_type=r.alarm_type,
                severity=r.severity,
                root_cause=r.root_cause,
                confidence_score=r.confidence_score,
                status=r.status,
                created_at=r.created_at,
                recommended_actions=actions,
            )
        )
    return items


@router.get("/events/{event_id}", response_model=RCAEventDetailResponse)
async def get_rca_event_detail(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: FirebaseUser = Depends(get_current_user),
):
    """Get full diagnostic report for the slide-out drawer."""
    stmt = select(RCAEvent).where(RCAEvent.id == event_id)
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail=f"RCA Event '{event_id}' not found.")

    try:
        actions = json.loads(record.recommended_actions_json) if record.recommended_actions_json else []
    except Exception:
        actions = []

    return RCAEventDetailResponse(
        id=record.id,
        asset_name=record.asset_name,
        node_id=record.node_id,
        alarm_type=record.alarm_type,
        severity=record.severity,
        root_cause=record.root_cause,
        confidence_score=record.confidence_score,
        status=record.status,
        created_at=record.created_at,
        recommended_actions=actions,
        telemetry_evidence=record.telemetry_evidence,
        sap_evidence=record.sap_evidence,
        sop_evidence=record.sop_evidence,
        raw_llm_response=record.raw_llm_response,
    )


@router.post("/trigger", response_model=RCAEventDetailResponse)
async def trigger_manual_rca(
    payload: RCATriggerRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: FirebaseUser = Depends(get_current_user),
):
    """Trigger on-demand RCA investigation for a Machine Health Card (Zone 2)."""
    orchestrator = getattr(request.app.state, "industrial_orchestrator", None)
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Industrial Orchestrator agent is not initialized.")

    try:
        record = await rca_engine.execute_rca(
            asset_name=payload.asset_name,
            node_id=payload.node_id,
            alarm_type=payload.alarm_type,
            severity=payload.severity,
            orchestrator=orchestrator,
            db_session=db,
            extra_context=payload.extra_context or "",
            force=True,  # Bypass debounce on manual click
        )

        try:
            actions = json.loads(record.recommended_actions_json) if record.recommended_actions_json else []
        except Exception:
            actions = []

        return RCAEventDetailResponse(
            id=record.id,
            asset_name=record.asset_name,
            node_id=record.node_id,
            alarm_type=record.alarm_type,
            severity=record.severity,
            root_cause=record.root_cause,
            confidence_score=record.confidence_score,
            status=record.status,
            created_at=record.created_at,
            recommended_actions=actions,
            telemetry_evidence=record.telemetry_evidence,
            sap_evidence=record.sap_evidence,
            sop_evidence=record.sop_evidence,
            raw_llm_response=record.raw_llm_response,
        )
    except Exception as e:
        logger.error("Manual RCA execution failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"RCA execution failed: {str(e)}")


@router.patch("/events/{event_id}/status")
async def update_rca_status(
    event_id: str,
    status: str = Query(..., pattern="^(open|acknowledged|resolved)$"),
    db: AsyncSession = Depends(get_db),
    current_user: FirebaseUser = Depends(get_current_user),
):
    """Update RCA status (e.g. acknowledge alert or mark resolved)."""
    stmt = select(RCAEvent).where(RCAEvent.id == event_id)
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail=f"RCA Event '{event_id}' not found.")

    record.status = status
    if status == "resolved":
        record.resolved_at = datetime.now(timezone.utc)
    await db.commit()

    return {"id": event_id, "status": status, "updated": True}
