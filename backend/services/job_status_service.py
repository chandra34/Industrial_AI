import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.database.models import IngestionJob
from backend.schemas.documents import UploadResponse

logger = logging.getLogger(__name__)


class JobStatusService:
    """Database-backed service to track status and results of background ingestion jobs."""

    async def create_job(self, db: AsyncSession, job_id: str, user_id: str) -> None:
        job = IngestionJob(id=job_id, user_id=user_id, status="pending")
        db.add(job)
        await db.commit()
        logger.info("Created background job status entry: %s for user %s", job_id, user_id)

    async def update_status(
        self,
        db: AsyncSession,
        job_id: str,
        status: str,
        result: UploadResponse | None = None,
        error: str | None = None,
    ) -> None:
        query_result = await db.execute(select(IngestionJob).filter(IngestionJob.id == job_id))
        job = query_result.scalars().first()
        if not job:
            logger.warning("Attempted to update non-existent job: %s", job_id)
            return
        job.status = status
        job.updated_at = datetime.now(timezone.utc)
        if result is not None:
            job.result_json = result.model_dump_json()
        if error is not None:
            job.error = error
        await db.commit()
        logger.info("Updated job %s status to %s", job_id, status)

    async def get_job(self, db: AsyncSession, job_id: str, user_id: str) -> dict[str, Any] | None:
        query_result = await db.execute(
            select(IngestionJob).filter(IngestionJob.id == job_id, IngestionJob.user_id == user_id)
        )
        job = query_result.scalars().first()
        if not job:
            return None
        result = None
        if job.result_json:
            result = UploadResponse(**json.loads(job.result_json))
        return {
            "status": job.status,
            "user_id": job.user_id,
            "result": result,
            "error": job.error,
        }
