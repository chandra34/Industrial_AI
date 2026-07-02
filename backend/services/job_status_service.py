import logging
from typing import Any
from backend.schemas.schemas import UploadResponse

logger = logging.getLogger(__name__)


class JobStatusService:
    """In-memory service to track status and results of background ingestion jobs."""

    def __init__(self) -> None:
        # Structure: { job_id: {"status": str, "user_id": str, "result": UploadResponse, "error": str} }
        self._jobs: dict[str, dict[str, Any]] = {}

    def create_job(self, job_id: str, user_id: str) -> None:
        self._jobs[job_id] = {
            "status": "pending",
            "user_id": user_id,
            "result": None,
            "error": None,
        }
        logger.info("Created background job status entry: %s for user %s", job_id, user_id)

    def update_status(
        self,
        job_id: str,
        status: str,
        result: UploadResponse | None = None,
        error: str | None = None,
    ) -> None:
        if job_id in self._jobs:
            self._jobs[job_id]["status"] = status
            if result is not None:
                self._jobs[job_id]["result"] = result
            if error is not None:
                self._jobs[job_id]["error"] = error
            logger.info("Updated job %s status to %s", job_id, status)
        else:
            logger.warning("Attempted to update non-existent job: %s", job_id)

    def get_job(self, job_id: str, user_id: str) -> dict[str, Any] | None:
        job = self._jobs.get(job_id)
        if job and job["user_id"] == user_id:
            return job
        return None
