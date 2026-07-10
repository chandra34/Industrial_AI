import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.config.settings import Settings
from backend.database.models import Document
from backend.services.storage import BaseStorageProvider
from backend.vectordb.milvus_db import MilvusStore

logger = logging.getLogger(__name__)


class DocumentServiceError(Exception):
    """Base exception for document service operations."""
    pass


class DocumentNotFoundError(DocumentServiceError):
    """Raised when a document is not found or the user does not have permission."""
    pass


class DocumentFileNotFoundError(DocumentServiceError):
    """Raised when a document exists in metadata but its raw file is missing on disk."""
    pass


class DocumentService:
    """Service to handle document operations: listing, deleting, and fetching download paths."""

    def __init__(self, settings: Settings, vector_store: MilvusStore, storage_provider: BaseStorageProvider) -> None:
        self.settings = settings
        self.vector_store = vector_store
        self.storage_provider = storage_provider

    async def list_user_documents(self, db: AsyncSession, user_id: str) -> list[dict]:
        """List all indexed documents for a specific user from the metadata database."""
        result = await db.execute(select(Document).filter(Document.user_id == user_id))
        docs = result.scalars().all()
        return [
            {
                "document_id": doc.id,
                "filename": doc.filename,
                "page_count": doc.page_count,
                "chunk_count": doc.chunk_count,
                "document_type": doc.document_type,
                "manufacturer": doc.manufacturer,
                "equipment": doc.equipment,
            }
            for doc in docs
        ]

    async def delete_user_document(self, db: AsyncSession, document_id: str, user_id: str) -> str:
        """Verify ownership and delete document vectors, metadata row, and stored file."""
        result = await db.execute(
            select(Document).filter(Document.id == document_id, Document.user_id == user_id)
        )
        doc = result.scalars().first()
        if not doc:
            raise DocumentNotFoundError("Document not found or access denied")

        # Delete vectors from Milvus
        await self.vector_store.delete_document(document_id, user_id)

        # Delete raw file via Storage Provider
        file_key = f"{document_id}_{doc.filename}"
        deleted_file = await self.storage_provider.delete_file(file_key)
        if deleted_file:
            logger.info("Deleted raw file: %s", file_key)
        else:
            logger.warning("Raw file not found for deletion: %s", file_key)

        # Delete metadata row from database
        await db.delete(doc)
        await db.commit()

        message = f"Successfully deleted document {document_id}"
        if not deleted_file:
            message += " (no raw file found in storage)"
        return message

    async def get_download_source(self, db: AsyncSession, document_id: str, user_id: str) -> dict:
        """Verify ownership and retrieve a presigned URL or raw bytes for downloading."""
        result = await db.execute(
            select(Document).filter(Document.id == document_id, Document.user_id == user_id)
        )
        doc = result.scalars().first()
        if not doc:
            raise DocumentNotFoundError("Document not found or access denied")

        file_key = f"{document_id}_{doc.filename}"

        # Try to generate a secure presigned redirect URL (best for S3/GCS)
        url = await self.storage_provider.get_download_url(file_key, doc.filename)
        if url:
            return {"type": "url", "url": url, "filename": doc.filename}

        # Fallback: stream raw bytes (local storage or providers without presigned URLs)
        file_bytes = await self.storage_provider.download_file(file_key)
        return {"type": "bytes", "bytes": file_bytes, "filename": doc.filename}
