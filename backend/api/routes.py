import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.concurrency import run_in_threadpool

from backend.config.settings import get_settings
from backend.models.schemas import (
    HealthResponse,
    QueryRequest,
    QueryResponse,
    SourceChunkResponse,
    UploadResponse,
    DocumentListResponse,
    DeleteResponse,
    DocumentItem,
)
from backend.rag.chunking import ChunkRecord
from backend.rag.pipeline import RAGPipeline
from backend.services.ingest_service import IngestService
from backend.vectordb.milvus_db import MilvusStore
from backend.api.auth import get_current_user, FirebaseUser

logger = logging.getLogger(__name__)
router = APIRouter()

UPLOAD_BUFFER_SIZE = 1024 * 1024  # 1MB chunk size for reading file uploads


def _get_state_service(request: Request, name: str):
    service = getattr(request.app.state, name, None)
    if service is None:
        raise HTTPException(status_code=503, detail=f"{name} is not ready")
    return service


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        app_name=settings.app_name,
        milvus_collection=settings.milvus_collection_name,
        llm_model=settings.llm_model,
    )


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(
    request: Request,
    file: UploadFile = File(...),
    current_user: FirebaseUser = Depends(get_current_user),
) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="A file name is required")
    if Path(file.filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024

    # Read safely in chunks to prevent memory explosion
    file_bytes = bytearray()
    while chunk := await file.read(UPLOAD_BUFFER_SIZE):  # Read in configured buffer size
        file_bytes.extend(chunk)
        if len(file_bytes) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds maximum size of {settings.max_upload_mb} MB",
            )
    
    # Cast back to bytes for downstream processing
    file_bytes = bytes(file_bytes)

    ingest_service: IngestService = _get_state_service(request, "ingest_service")

    try:
        result = await ingest_service.ingest_pdf(file_bytes, file.filename, current_user.uid)
    except Exception as exc:
        logger.exception("Upload failed for %s", file.filename)
        raise HTTPException(status_code=500, detail="Failed to process and index the uploaded PDF document.") from exc

    return UploadResponse(
        document_id=result.document_id,
        filename=result.filename,
        stored_path=result.stored_path,
        page_count=result.page_count,
        chunk_count=result.chunk_count,
        embedded_count=result.embedded_count,
    )


@router.post("/query", response_model=QueryResponse)
async def query_documents(
    request: Request,
    payload: QueryRequest,
    current_user: FirebaseUser = Depends(get_current_user),
) -> QueryResponse:
    pipeline: RAGPipeline = _get_state_service(request, "rag_pipeline")

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
                source_filename=chunk.source_filename,
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
    request: Request,
    current_user: FirebaseUser = Depends(get_current_user),
) -> DocumentListResponse:
    vector_store: MilvusStore = _get_state_service(request, "vector_store")
    try:
        docs = await vector_store.list_documents(current_user.uid)
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
    request: Request,
    document_id: str,
    current_user: FirebaseUser = Depends(get_current_user),
) -> DeleteResponse:
    vector_store: MilvusStore = _get_state_service(request, "vector_store")
    settings = get_settings()
    upload_dir = settings.resolved_upload_dir

    # Verify the document belongs to the current user before any deletion
    try:
        docs = await vector_store.list_documents(current_user.uid)
        target_doc = next((d for d in docs if d["document_id"] == document_id), None)
        if not target_doc:
            raise HTTPException(status_code=404, detail="Document not found or access denied")
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to verify document ownership for %s", document_id)
        raise HTTPException(status_code=500, detail="Failed to verify document ownership.") from exc

    try:
        await vector_store.delete_document(document_id, current_user.uid)
        
        deleted_file = False
        exact_file_path = upload_dir / f"{document_id}_{target_doc['filename']}"
        if exact_file_path.exists():
            try:
                exact_file_path.unlink()
                deleted_file = True
                logger.info("Deleted raw PDF file: %s", exact_file_path)
            except Exception as e:
                logger.warning("Could not delete file %s from disk: %s", exact_file_path, e)

        # Rebuild BM25 index without the deleted document's chunks
        bm25_service = getattr(request.app.state, "bm25_service", None)
        if bm25_service:
            try:
                remaining_texts = await vector_store.get_all_chunk_texts(current_user.uid)
                # Build a minimal list of chunk-like objects for rebuild
                remaining_chunks = [
                    ChunkRecord(
                        document_id="", source_filename="",
                        page_number=0, chunk_index=i, text=t,
                    )
                    for i, t in enumerate(remaining_texts)
                ]
                await run_in_threadpool(
                    bm25_service.delete_document_from_index,
                    current_user.uid, remaining_chunks,
                )
                logger.info("Rebuilt BM25 index for user %s after document deletion", current_user.uid)
            except Exception as bm25_exc:
                logger.warning("BM25 index rebuild failed after delete: %s", bm25_exc)

        msg = f"Successfully deleted document {document_id}"
        if not deleted_file:
            msg += " (no raw file found on disk)"
        return DeleteResponse(message=msg)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to delete document %s", document_id)
        raise HTTPException(status_code=500, detail="An error occurred while deleting the document.") from exc


@router.get("/documents/{document_id}/download")
async def download_document(
    request: Request,
    document_id: str,
    current_user: FirebaseUser = Depends(get_current_user),
) -> FileResponse:
    settings = get_settings()
    upload_dir = settings.resolved_upload_dir
    vector_store: MilvusStore = _get_state_service(request, "vector_store")

    try:
        # Check if the document belongs to the user
        docs = await vector_store.list_documents(current_user.uid)
        target_doc = next((d for d in docs if d["document_id"] == document_id), None)
        if not target_doc:
            raise HTTPException(status_code=404, detail="Document not found or access denied")
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to authorize document access")
        raise HTTPException(status_code=500, detail="Failed to authorize document access.") from exc

    if not upload_dir.exists():
        raise HTTPException(status_code=404, detail="Uploads directory does not exist")

    target_file = upload_dir / f"{document_id}_{target_doc['filename']}"

    if not target_file.exists():
        raise HTTPException(status_code=404, detail="Document file not found on disk")

    return FileResponse(
        path=target_file,
        filename=target_doc['filename'],
        media_type="application/pdf"
    )

