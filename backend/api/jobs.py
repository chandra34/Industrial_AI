import base64
import logging
from pathlib import Path
from uuid import uuid4
import fitz

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from redis import Redis
from rq import Queue
from rq.serializers import JSONSerializer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config.settings import get_settings
from backend.schemas.jobs import UploadJobAcceptedResponse, JobStatusResponse
from backend.api.auth import get_current_user, FirebaseUser
from backend.api.dependencies import get_job_status_service, get_db
from backend.services.job_status_service import JobStatusService
from backend.tasks import run_ingest_task
from backend.services.storage import create_storage_provider

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
    current_user: FirebaseUser = Depends(get_current_user),
    job_status_service: JobStatusService = Depends(get_job_status_service),
    db: AsyncSession = Depends(get_db),
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

    # Verify document page limit using PyMuPDF (fitz)
    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            page_count = doc.page_count
        if page_count > settings.max_page_limit:
            logger.warning("Upload rejected: file has %d pages, limit is %d", page_count, settings.max_page_limit)
            raise HTTPException(
                status_code=413,
                detail=f"Document exceeds the maximum limit of {settings.max_page_limit} pages. Your file has {page_count} pages.",
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to verify PDF structure during upload")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to parse PDF structure. The file might be corrupted.",
        ) from exc

    job_id = uuid4().hex
    await job_status_service.create_job(db, job_id, current_user.uid)

    # Initialize storage provider and upload the PDF file to temporary storage
    storage_provider = create_storage_provider(settings)
    safe_filename = Path(file.filename).name or "document.pdf"
    file_key = f"temp_{job_id}_{safe_filename}"
    await storage_provider.upload_file(file_bytes, file_key)

    metadata = {
        "document_type": document_type,
        "manufacturer": manufacturer,
        "equipment": equipment,
    }

    task_queue.enqueue(
        run_ingest_task,
        job_id,
        file_key,
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
    db: AsyncSession = Depends(get_db),
) -> JobStatusResponse:
    """Retrieve status and result of a background document ingestion job."""
    job = await job_status_service.get_job(db, job_id, current_user.uid)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or access denied")

    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        message=f"Job status is {job['status']}",
        result=job["result"],
        error=job["error"],
    )
