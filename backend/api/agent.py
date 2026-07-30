import logging
from fastapi import APIRouter, Depends, HTTPException

from backend.agents.schemas import AgentQueryRequest, AgentResponse
from backend.agents.orchestrator import IndustrialOrchestrator
from backend.api.auth import get_current_user, FirebaseUser
from backend.api.dependencies import get_industrial_orchestrator

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/query", response_model=AgentResponse)
async def query_agent(
    payload: AgentQueryRequest,
    current_user: FirebaseUser = Depends(get_current_user),
    orchestrator: IndustrialOrchestrator = Depends(get_industrial_orchestrator),
) -> AgentResponse:
    """Execute multi-step industrial AI agent reasoning and tool orchestration."""
    try:
        return await orchestrator.run(payload, user_id=current_user.uid)
    except Exception as exc:
        logger.exception("Agent orchestrator execution failed")
        raise HTTPException(
            status_code=500,
            detail=f"Agent orchestration error: {str(exc)}"
        ) from exc
