import logging
from pathlib import Path
from backend.config.settings import Settings
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

    async def list_user_documents(self, user_id: str) -> list[dict]:
        """List all indexed documents for a specific user."""
        return await self.vector_store.list_documents(user_id)

    async def delete_user_document(self, document_id: str, user_id: str) -> str:
        """Verify ownership and delete document vectors and physical file."""
        docs = await self.list_user_documents(user_id)
        target_doc = next((d for d in docs if d["document_id"] == document_id), None)
        if not target_doc:
            raise DocumentNotFoundError("Document not found or access denied")

        # Delete vectors from Milvus
        await self.vector_store.delete_document(document_id, user_id)

        # Delete raw file from local storage
        deleted_file = False
        exact_file_path = self.upload_dir / f"{document_id}_{target_doc['filename']}"
        if exact_file_path.exists():
            try:
                exact_file_path.unlink()
                deleted_file = True
                logger.info("Deleted raw PDF file: %s", exact_file_path)
            except Exception as e:
                logger.warning("Could not delete file %s from disk: %s", exact_file_path, e)

        message = f"Successfully deleted document {document_id}"
        if not deleted_file:
            message += " (no raw file found on disk)"
        return message

    async def get_download_path(self, document_id: str, user_id: str) -> tuple[Path, str]:
        """Verify ownership and retrieve the physical path and pretty name for downloading."""
        docs = await self.list_user_documents(user_id)
        target_doc = next((d for d in docs if d["document_id"] == document_id), None)
        if not target_doc:
            raise DocumentNotFoundError("Document not found or access denied")

        if not self.upload_dir.exists():
            raise DocumentFileNotFoundError("Uploads directory does not exist")

        target_file = self.upload_dir / f"{document_id}_{target_doc['filename']}"
        if not target_file.exists():
            raise DocumentFileNotFoundError("Document file not found on disk")

        return target_file, target_doc['filename']
