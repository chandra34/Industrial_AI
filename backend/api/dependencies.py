from fastapi import Request
from backend.services.ingest_service import IngestService
from backend.rag.pipeline import RAGPipeline
from backend.services.document_service import DocumentService
from backend.services.job_status_service import JobStatusService
from backend.services.storage import BaseStorageProvider
from backend.database.session import get_db  # noqa: F401 – re-exported for route injection


def get_ingest_service(request: Request) -> IngestService:
    """FastAPI dependency to retrieve the IngestService from app state."""
    return request.app.state.ingest_service


def get_rag_pipeline(request: Request) -> RAGPipeline:
    """FastAPI dependency to retrieve the RAGPipeline from app state."""
    return request.app.state.rag_pipeline


def get_document_service(request: Request) -> DocumentService:
    """FastAPI dependency to retrieve the DocumentService from app state."""
    return request.app.state.document_service


def get_job_status_service(request: Request) -> JobStatusService:
    """FastAPI dependency to retrieve the JobStatusService from app state."""
    return request.app.state.job_status_service


def get_storage_provider(request: Request) -> BaseStorageProvider:
    """FastAPI dependency to retrieve the BaseStorageProvider from app state."""
    return request.app.state.storage_provider
