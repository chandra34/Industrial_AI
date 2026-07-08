import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.config.settings import Settings
from backend.database.models import Document
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

    def __init__(self, settings: Settings, vector_store: MilvusStore) -> None:
        self.settings = settings
        self.vector_store = vector_store
        self.upload_dir = settings.resolved_upload_dir

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
                "revision": doc.revision,
                "language": doc.language,
            }
            for doc in docs
        ]

    async def delete_user_document(self, db: AsyncSession, document_id: str, user_id: str) -> str:
        """Verify ownership and delete document vectors, metadata row, and physical file."""
        result = await db.execute(
            select(Document).filter(Document.id == document_id, Document.user_id == user_id)
        )
        doc = result.scalars().first()
        if not doc:
            raise DocumentNotFoundError("Document not found or access denied")

        # Delete vectors from Milvus
        await self.vector_store.delete_document(document_id, user_id)

        # Delete raw file from local storage
        deleted_file = False
        exact_file_path = self.upload_dir / f"{document_id}_{doc.filename}"
        if exact_file_path.exists():
            try:
                exact_file_path.unlink()
                deleted_file = True
                logger.info("Deleted raw PDF file: %s", exact_file_path)
            except Exception as e:
                logger.warning("Could not delete file %s from disk: %s", exact_file_path, e)

        # Delete metadata row from database
        await db.delete(doc)
        await db.commit()

        message = f"Successfully deleted document {document_id}"
        if not deleted_file:
            message += " (no raw file found on disk)"
        return message

    async def get_download_path(self, db: AsyncSession, document_id: str, user_id: str) -> tuple[Path, str]:
        """Verify ownership and retrieve the physical path and pretty name for downloading."""
        result = await db.execute(
            select(Document).filter(Document.id == document_id, Document.user_id == user_id)
        )
        doc = result.scalars().first()
        if not doc:
            raise DocumentNotFoundError("Document not found or access denied")

        if not self.upload_dir.exists():
            raise DocumentFileNotFoundError("Uploads directory does not exist")

        target_file = self.upload_dir / f"{document_id}_{doc.filename}"
        if not target_file.exists():
            raise DocumentFileNotFoundError("Document file not found on disk")

        return target_file, doc.filename
