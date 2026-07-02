from dataclasses import dataclass
from pathlib import Path
import logging
from uuid import uuid4

from backend.config.settings import Settings
from backend.rag.embeddings import EmbeddingProvider
from backend.ingestion.pipeline import get_parser
from backend.vectordb.milvus_db import MilvusStore
from fastapi.concurrency import run_in_threadpool

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
    """Parse PDFs, chunk text, embed vectors, and persist them to Milvus.

    Milvus handles sparse BM25 vector generation natively during insertion,
    so no separate BM25 index update step is required.
    """

    def __init__(
        self,
        settings: Settings,
        vector_store: MilvusStore,
        embedding_service: EmbeddingProvider,
    ) -> None:
        self.settings = settings
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.upload_dir = settings.resolved_upload_dir
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def _save_upload(self, file_bytes: bytes, original_name: str) -> tuple[Path, str]:
        safe_name = Path(original_name).name or "document.pdf"
        document_id = uuid4().hex
        stored_path = self.upload_dir / f"{document_id}_{safe_name}"
        stored_path.write_bytes(file_bytes)
        return stored_path, document_id

    async def ingest_pdf(self, file_bytes: bytes, original_name: str, user_id: str) -> IngestionResult:
        """Ingest a PDF for ``user_id`` and return indexing metadata."""
        import time
        from backend.utils.logging_context import document_id_var
        
        logger.info("Upload flow: request received | filename: %s | size: %d bytes", original_name, len(file_bytes))
        
        if not file_bytes:
            raise ValueError("Uploaded file is empty")

        stored_path, document_id = self._save_upload(file_bytes, original_name)
        document_id_var.set(document_id)
        
        logger.info("Upload flow: file validation passed | document_id: %s | stored_path: %s", document_id, stored_path)

        try:
            # Document parsing and chunking
            start_parse_chunk = time.perf_counter()
            try:
                parser = get_parser(self.settings)
                chunks = await run_in_threadpool(
                    parser.parse,
                    file_bytes,
                    document_id=document_id,
                    source_filename=stored_path.name,
                )
            except Exception as parse_err:
                logger.exception("Upload flow: Failed to parse and chunk uploaded PDF %s", original_name)
                raise parse_err
            duration_parse_chunk = time.perf_counter() - start_parse_chunk
            logger.info(
                "Upload flow: PDF parsed and chunked | parser: %s | chunks: %d | duration: %.3fs",
                self.settings.document_parser,
                len(chunks),
                duration_parse_chunk,
            )

            if not chunks:
                raise ValueError("PDF parsed successfully but no chunks were generated")

            # Embedding generation
            start_embed = time.perf_counter()
            embeddings = await self.embedding_service.embed_texts(chunk.text for chunk in chunks)
            duration_embed = time.perf_counter() - start_embed
            logger.info("Upload flow: embeddings generated | count: %d | duration: %.3fs", len(embeddings), duration_embed)
            
            if embeddings.size == 0:
                raise ValueError("Embedding generation returned no vectors")

            # Vector store insert
            start_store = time.perf_counter()
            stored_count = await self.vector_store.insert_chunks(chunks, embeddings, user_id)
            duration_store = time.perf_counter() - start_store
            logger.info("Upload flow: vectors stored | count: %d | duration: %.3fs", stored_count, duration_store)
            
            logger.info("Indexed document %s for user %s with %s chunks", document_id, user_id, stored_count)

            logger.info("Upload flow: request completed successfully | document_id: %s", document_id)
            return IngestionResult(
                document_id=document_id,
                filename=original_name,
                stored_path=str(stored_path),
                page_count=max((c.page_number for c in chunks), default=1),
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

