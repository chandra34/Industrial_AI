from fastapi import Request
from backend.services.ingest_service import IngestService
from backend.rag.pipeline import RAGPipeline
from backend.services.document_service import DocumentService


def get_ingest_service(request: Request) -> IngestService:
    """FastAPI dependency to retrieve the IngestService from app state."""
    return request.app.state.ingest_service


def get_rag_pipeline(request: Request) -> RAGPipeline:
    """FastAPI dependency to retrieve the RAGPipeline from app state."""
    return request.app.state.rag_pipeline


def get_document_service(request: Request) -> DocumentService:
    """FastAPI dependency to retrieve the DocumentService from app state."""
    return request.app.state.document_service
