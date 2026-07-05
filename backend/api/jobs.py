import base64
import logging
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from redis import Redis
from rq import Queue
from rq.serializers import JSONSerializer
from sqlalchemy.orm import Session

from backend.config.settings import get_settings
from backend.schemas.schemas import UploadJobAcceptedResponse, JobStatusResponse
from backend.api.auth import get_current_user, FirebaseUser
from backend.api.dependencies import get_job_status_service, get_db
from backend.services.job_status_service import JobStatusService
from backend.tasks import run_ingest_task

logger = logging.getLogger(__name__)
router = APIRouter()

settings = get_settings()
redis_conn = Redis.from_url(settings.redis_url)
task_queue = Queue("ingestion", connection=redis_conn, serializer=JSONSerializer)

UPLOAD_BUFFER_SIZE = 1024 * 1024  # 1MB chunk size for reading file uploads


@router.post("/upload", response_model=UploadJobAcceptedResponse, status_code=202)
async def upload_pdf(
    file: UploadFile = File(...),
    document_type: str | None = Form(None),
    manufacturer: str | None = Form(None),
    equipment: str | None = Form(None),
    revision: str | None = Form(None),
    language: str | None = Form(None),
    current_user: FirebaseUser = Depends(get_current_user),
    job_status_service: JobStatusService = Depends(get_job_status_service),
    db: Session = Depends(get_db),
) -> UploadJobAcceptedResponse:
    """Accept a PDF upload, start ingestion in the background, and return a job identifier."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="A file name is required")
    if Path(file.filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024

    # Read safely in chunks to prevent memory explosion
    try:
        file_bytes = bytearray()
        while chunk := await file.read(UPLOAD_BUFFER_SIZE):  # Read in configured buffer size
            file_bytes.extend(chunk)
            if len(file_bytes) > max_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=f"File exceeds maximum size of {settings.max_upload_mb} MB",
                )
    finally:
        await file.close()

    # Cast back to bytes for downstream processing
    file_bytes = bytes(file_bytes)

    job_id = uuid4().hex
    job_status_service.create_job(db, job_id, current_user.uid)

    file_bytes_b64 = base64.b64encode(file_bytes).decode("utf-8")

    metadata = {
        "document_type": document_type,
        "manufacturer": manufacturer,
        "equipment": equipment,
        "revision": revision,
        "language": language,
    }

    task_queue.enqueue(
        run_ingest_task,
        job_id,
        file_bytes_b64,
        file.filename,
        current_user.uid,
        metadata=metadata,
        job_id=job_id,
    )

    return UploadJobAcceptedResponse(
        job_id=job_id,
        message="Document upload accepted. Processing in the background."
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    current_user: FirebaseUser = Depends(get_current_user),
    job_status_service: JobStatusService = Depends(get_job_status_service),
    db: Session = Depends(get_db),
) -> JobStatusResponse:
    """Retrieve status and result of a background document ingestion job."""
    job = job_status_service.get_job(db, job_id, current_user.uid)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or access denied")

    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        message=f"Job status is {job['status']}",
        result=job["result"],
        error=job["error"],
    )
