import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from uuid import uuid4

from redis import Redis
from rq import Queue

from backend.config.settings import get_settings
from backend.schemas.schemas import (
    HealthResponse,
    QueryRequest,
    QueryResponse,
    SourceChunkResponse,
    UploadResponse,
    DocumentListResponse,
    DeleteResponse,
    DocumentItem,
    UploadJobAcceptedResponse,
    JobStatusResponse,
)
from backend.rag.pipeline import RAGPipeline
from backend.services.ingest_service import IngestService
from backend.services.document_service import (
    DocumentService,
    DocumentNotFoundError,
    DocumentFileNotFoundError,
)
from backend.services.job_status_service import JobStatusService
from sqlalchemy.orm import Session
from backend.api.auth import get_current_user, FirebaseUser
from backend.api.dependencies import (
    get_ingest_service,
    get_rag_pipeline,
    get_document_service,
    get_job_status_service,
    get_db,
)
from backend.database.session import SessionLocal
from backend.tasks import run_ingest_task

logger = logging.getLogger(__name__)
router = APIRouter()

settings = get_settings()
redis_conn = Redis.from_url(settings.redis_url)
task_queue = Queue("ingestion", connection=redis_conn)

UPLOAD_BUFFER_SIZE = 1024 * 1024  # 1MB chunk size for reading file uploads



@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Return application health and configured service identifiers."""
    settings = get_settings()
    return HealthResponse(
        app_name=settings.app_name,
        milvus_collection=settings.milvus_collection_name,
        llm_model=settings.llm_model,
    )


@router.post("/upload", response_model=UploadJobAcceptedResponse, status_code=202)
async def upload_pdf(
    file: UploadFile = File(...),
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

    task_queue.enqueue(
        run_ingest_task,
        job_id,
        file_bytes,
        file.filename,
        current_user.uid,
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


def _clean_filename(filename: str, doc_id: str) -> str:
    if filename and filename.startswith(f"{doc_id}_"):
        return filename[len(doc_id) + 1 :]
    return filename or "Unknown"


@router.post("/query", response_model=QueryResponse)
async def query_documents(
    payload: QueryRequest,
    current_user: FirebaseUser = Depends(get_current_user),
    pipeline: RAGPipeline = Depends(get_rag_pipeline),
) -> QueryResponse:
    """Run RAG retrieval and generation for a user question."""

    try:
        result = await pipeline.answer_question(payload.question, user_id=current_user.uid, top_k=payload.top_k)
    except Exception as exc:
        logger.exception("Query failed")
        raise HTTPException(status_code=500, detail="An internal server error occurred while processing your query.") from exc

    return QueryResponse(
        question=payload.question,
        answer=result.answer,
        source_chunks=[
            SourceChunkResponse(
                document_id=chunk.document_id,
                source_filename=_clean_filename(chunk.source_filename, chunk.document_id),
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                score=chunk.score,
                chunk_text=chunk.chunk_text,
            )
            for chunk in result.sources
        ],
        retrieved_chunk_count=len(result.sources),
    )


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    current_user: FirebaseUser = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
    db: Session = Depends(get_db),
) -> DocumentListResponse:
    """List indexed documents belonging to the authenticated user."""
    try:
        docs = await document_service.list_user_documents(db, current_user.uid)
        items = [
            DocumentItem(
                document_id=doc["document_id"],
                filename=doc["filename"],
                page_count=doc["page_count"],
                chunk_count=doc["chunk_count"],
            )
            for doc in docs
        ]
        return DocumentListResponse(documents=items)
    except Exception as exc:
        logger.exception("Failed to list documents")
        raise HTTPException(status_code=500, detail="Failed to retrieve document list.") from exc


@router.delete("/documents/{document_id}", response_model=DeleteResponse)
async def delete_document(
    document_id: str,
    current_user: FirebaseUser = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
    db: Session = Depends(get_db),
) -> DeleteResponse:
    """Delete a document's vectors and raw file for the user."""
    from backend.utils.logging_context import document_id_var
    document_id_var.set(document_id)

    try:
        msg = await document_service.delete_user_document(db, document_id, current_user.uid)
        return DeleteResponse(message=msg)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Failed to delete document %s", document_id)
        raise HTTPException(status_code=500, detail="An error occurred while deleting the document.") from exc


@router.get("/documents/{document_id}/download")
async def download_document(
    document_id: str,
    current_user: FirebaseUser = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Download the original PDF file for an owned document."""
    from backend.utils.logging_context import document_id_var
    document_id_var.set(document_id)

    try:
        file_path, filename = await document_service.get_download_path(db, document_id, current_user.uid)
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="application/pdf"
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except DocumentFileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Failed to download document %s", document_id)
        raise HTTPException(status_code=500, detail="Failed to authorize or locate document download path.") from exc

