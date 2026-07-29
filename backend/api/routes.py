from fastapi import APIRouter

from backend.api.health import router as health_router
from backend.api.jobs import router as jobs_router
from backend.api.query import router as query_router
from backend.api.documents import router as documents_router
from backend.api.agent import router as agent_router

router = APIRouter()

# Include resource sub-routers
router.include_router(health_router)
router.include_router(jobs_router)
router.include_router(query_router)
router.include_router(documents_router)
router.include_router(agent_router, prefix="/agent", tags=["Agent Orchestrator"])

