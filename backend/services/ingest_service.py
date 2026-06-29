from dataclasses import dataclass
from pathlib import Path
import logging
from uuid import uuid4

from backend.config.settings import Settings
from backend.pdf.parser import PDFParseError, extract_pages_from_bytes
from backend.rag.chunking import chunk_pages
from backend.rag.embeddings import EmbeddingProvider
from backend.services.bm25_service import BM25Service
from backend.vectordb.milvus_db import MilvusStore

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IngestionResult:
    document_id: str
    filename: str
    stored_path: str
    page_count: int
    chunk_count: int
    embedded_count: int


class IngestService:
    def __init__(
        self,
        settings: Settings,
        vector_store: MilvusStore,
        embedding_service: EmbeddingProvider,
        bm25_service: BM25Service | None = None,
    ) -> None:
        self.settings = settings
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.bm25_service = bm25_service
        self.upload_dir = settings.resolved_upload_dir
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def _save_upload(self, file_bytes: bytes, original_name: str) -> tuple[Path, str]:
        safe_name = Path(original_name).name or "document.pdf"
        document_id = uuid4().hex
        stored_path = self.upload_dir / f"{document_id}_{safe_name}"
        stored_path.write_bytes(file_bytes)
        return stored_path, document_id

    async def ingest_pdf(self, file_bytes: bytes, original_name: str, user_id: str) -> IngestionResult:
        if not file_bytes:
            raise ValueError("Uploaded file is empty")

        stored_path, document_id = self._save_upload(file_bytes, original_name)

        try:
            try:
                pages = extract_pages_from_bytes(file_bytes)
            except PDFParseError:
                logger.exception("Failed to parse uploaded PDF %s", original_name)
                raise

            if not pages:
                raise ValueError("No extractable text found in the uploaded PDF")

            chunks = chunk_pages(
                pages,
                document_id=document_id,
                source_filename=stored_path.name,
                settings=self.settings,
            )
            if not chunks:
                raise ValueError("PDF parsed successfully but no chunks were generated")

            embeddings = self.embedding_service.embed_texts(chunk.text for chunk in chunks)
            if embeddings.size == 0:
                raise ValueError("Embedding generation returned no vectors")

            stored_count = await self.vector_store.insert_chunks(chunks, embeddings, user_id)
            logger.info("Indexed document %s for user %s with %s chunks", document_id, user_id, stored_count)

            # Update BM25 sparse index (non-critical — failure here must not break ingestion)
            if self.bm25_service:
                try:
                    self.bm25_service.add_to_index(user_id, chunks)
                    logger.info("Updated BM25 index for user %s", user_id)
                except Exception as bm25_exc:
                    logger.warning("BM25 index update failed for user %s: %s", user_id, bm25_exc)

            return IngestionResult(
                document_id=document_id,
                filename=original_name,
                stored_path=str(stored_path),
                page_count=len(pages),
                chunk_count=len(chunks),
                embedded_count=stored_count,
            )
        except Exception:
            # Clean up the orphaned file on disk since ingestion failed
            if stored_path.exists():
                try:
                    stored_path.unlink()
                    logger.info("Cleaned up orphaned file from disk due to ingestion failure: %s", stored_path)
                except Exception as e:
                    logger.warning("Could not delete orphaned file %s: %s", stored_path, e)
            raise

