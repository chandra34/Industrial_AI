import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.database.models import IngestionJob
from backend.schemas.schemas import UploadResponse

logger = logging.getLogger(__name__)


class JobStatusService:
    """Database-backed service to track status and results of background ingestion jobs."""

    def create_job(self, db: Session, job_id: str, user_id: str) -> None:
        job = IngestionJob(id=job_id, user_id=user_id, status="pending")
        db.add(job)
        db.commit()
        logger.info("Created background job status entry: %s for user %s", job_id, user_id)

    def update_status(
        self,
        db: Session,
        job_id: str,
        status: str,
        result: UploadResponse | None = None,
        error: str | None = None,
    ) -> None:
        job = db.query(IngestionJob).filter_by(id=job_id).first()
        if not job:
            logger.warning("Attempted to update non-existent job: %s", job_id)
            return
        job.status = status
        job.updated_at = datetime.now(timezone.utc)
        if result is not None:
            job.result_json = result.model_dump_json()
        if error is not None:
            job.error = error
        db.commit()
        logger.info("Updated job %s status to %s", job_id, status)

    def get_job(self, db: Session, job_id: str, user_id: str) -> dict[str, Any] | None:
        job = db.query(IngestionJob).filter_by(id=job_id, user_id=user_id).first()
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
