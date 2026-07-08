import logging

from fastapi import APIRouter, Depends, Request, Response, status
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config.settings import get_settings
from backend.schemas.health import HealthResponse
from backend.api.dependencies import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

settings = get_settings()
redis_conn = Redis.from_url(settings.redis_url)


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Return application health and configured service identifiers."""
    settings = get_settings()
    return HealthResponse(
        app_name=settings.app_name,
        milvus_collection=settings.milvus_collection_name,
        llm_model=settings.llm_model,
    )


@router.get("/healthz/liveness")
async def liveness() -> dict:
    """Fast liveness check to verify the process is alive."""
    return {"status": "ok"}


@router.get("/healthz/readiness")
async def readiness(
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Deep readiness check to verify connections to sqlite, redis, and milvus."""
    status_details = {}
    is_healthy = True

    # 1. Check Database (SQLAlchemy / SQLite)
    try:
        from sqlalchemy import text
        await db.execute(text("SELECT 1"))
        status_details["database"] = "ok"
    except Exception as e:
        logger.error("Readiness check: database failed: %s", e)
        status_details["database"] = f"error: {str(e)}"
        is_healthy = False

    # 2. Check Redis
    try:
        redis_conn.ping()
        status_details["redis"] = "ok"
    except Exception as e:
        logger.error("Readiness check: redis failed: %s", e)
        status_details["redis"] = f"error: {str(e)}"
        is_healthy = False

    # 3. Check Milvus
    try:
        vector_store = getattr(request.app.state, "vector_store", None)
        if vector_store and vector_store.check_health():
            status_details["milvus"] = "ok"
        else:
            status_details["milvus"] = "error: connection failed or vector store not initialized"
            is_healthy = False
    except Exception as e:
        logger.error("Readiness check: milvus failed: %s", e)
        status_details["milvus"] = f"error: {str(e)}"
        is_healthy = False

    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unhealthy", **status_details}

    return {"status": "healthy", **status_details}
