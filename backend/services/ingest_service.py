from dataclasses import dataclass
from pathlib import Path
import logging
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from backend.config.settings import Settings
from backend.database.models import Document
from backend.rag.embeddings import EmbeddingProvider
from backend.rag.llm import LLMProvider
from backend.ingestion.pipeline import get_parser
from backend.services.storage import BaseStorageProvider
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
    document_type: str | None = None
    manufacturer: str | None = None
    equipment: str | None = None


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
        llm_service: LLMProvider,
        storage_provider: BaseStorageProvider,
    ) -> None:
        self.settings = settings
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.llm_service = llm_service
        self.storage_provider = storage_provider

    async def _save_upload(self, file_bytes: bytes, original_name: str) -> tuple[str, str]:
        safe_name = Path(original_name).name or "document.pdf"
        document_id = uuid4().hex
        file_key = f"{document_id}_{safe_name}"
        stored_path = await self.storage_provider.upload_file(file_bytes, file_key)
        return stored_path, document_id

    async def _extract_metadata_via_llm(self, doc_text_sample: str) -> dict:
        """Use the LLM service to extract document metadata using strict JSON schema."""
        import json
        from pydantic import BaseModel, Field

        class DocumentMetadata(BaseModel):
            model_config = {"extra": "forbid"}

            document_type: str = Field(description="One of: 'OEM Manual', 'SOP', 'LOTO Procedure', 'Work Instruction', 'Safety Rules', or 'Unknown'")
            manufacturer: str = Field(description="Equipment manufacturer name, or 'Unknown'")
            equipment: str = Field(description="Specific equipment model or name, or 'Unknown'")

        # Validate that the API key for the active provider is configured
        active_provider = self.settings.llm_provider.lower().strip()
        api_key_configured = False

        if active_provider == "groq" and self.settings.groq_api_key:
            api_key_configured = True
        elif active_provider == "openai" and self.settings.openai_api_key:
            api_key_configured = True
        elif active_provider == "gemini" and self.settings.gemini_api_key:
            api_key_configured = True
        elif active_provider == "anthropic" and self.settings.anthropic_api_key:
            api_key_configured = True

        if not api_key_configured:
            logger.warning("LLM API key for active provider '%s' not configured; skipping LLM metadata extraction", active_provider)
            return {}
            
        try:
            prompt = (
                "You are an industrial safety document analyzer. Extract document metadata from the following text sample "
                "taken from the beginning of a document. You must return a valid JSON object strictly matching the schema. "
                "CRITICAL: For the 'manufacturer' and 'equipment' fields, normalize the values to lowercase, singular form "
                "(e.g. use 'centrifugal pump' instead of 'Centrifugal Pumps', 'boiler' instead of 'Boilers', 'siemens' instead of 'Siemens').\n\n"
                f"Text Sample:\n{doc_text_sample[:4000]}"
            )
            messages = [{"role": "user", "content": prompt}]
            content = await self.llm_service.generate_structured_output(
                messages=messages,
                response_model=DocumentMetadata,
                temperature=0.0
            )
            
            logger.info("Raw LLM metadata extraction response: %s", content)
            return json.loads(content)
        except Exception as e:
            logger.exception("Failed to extract metadata via %s structured outputs: %s", active_provider, e)
            return {}

    async def ingest_pdf(self, file_bytes: bytes, original_name: str, user_id: str, db: AsyncSession | None = None, metadata: dict | None = None) -> IngestionResult:
        """Parse PDFs, chunk text, embed vectors, and persist them to Milvus."""
        import time
        from backend.utils.logging_context import document_id_var
        
        logger.info("Upload flow: request received | filename: %s | size: %d bytes", original_name, len(file_bytes))
        
        stored_path = None
        document_id = None

        try:
            if not file_bytes:
                raise ValueError("Uploaded file is empty")

            safe_filename = Path(original_name).name or "document.pdf"
            stored_path, document_id = await self._save_upload(file_bytes, safe_filename)
            document_id_var.set(document_id)
            
            logger.info("Upload flow: file validation passed | document_id: %s | stored_path: %s", document_id, stored_path)

            # Document parsing and chunking
            start_parse_chunk = time.perf_counter()
            try:
                parser = get_parser(self.settings)
                file_key = f"{document_id}_{safe_filename}"
                chunks = await run_in_threadpool(
                    parser.parse,
                    file_bytes,
                    document_id=document_id,
                    source_filename=file_key,
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

            # Metadata extraction and resolution
            final_meta = {
                "document_type": "Unknown",
                "manufacturer": "Unknown",
                "equipment": "Unknown",
            }
            if metadata:
                # Merge user overrides
                for k, v in metadata.items():
                    if v:
                        final_meta[k] = v

            # Check if any fields need LLM extraction (i.e. they are still "Unknown")
            needs_extraction = any(final_meta[k] == "Unknown" for k in ["document_type", "manufacturer", "equipment"])
            if needs_extraction:
                # Take sample text from first few chunks
                sample_chunks = [c.text for c in chunks[:5]]
                sample_text = "\n".join(sample_chunks)
                logger.info("Triggering Groq fallback metadata extraction on text sample")
                llm_meta = await self._extract_metadata_via_llm(sample_text)
                for k in ["document_type", "manufacturer", "equipment"]:
                    if final_meta.get(k) == "Unknown" and llm_meta.get(k):
                        final_meta[k] = llm_meta[k]

            # Normalize manufacturer and equipment strings to lowercase and strip whitespace
            mfr = final_meta.get("manufacturer")
            equip = final_meta.get("equipment")
            final_meta["manufacturer"] = mfr.strip().lower() if mfr else "unknown"
            final_meta["equipment"] = equip.strip().lower() if equip else "unknown"

            # In-memory chunk enrichment with resolved metadata
            for chunk in chunks:
                chunk.document_type = final_meta.get("document_type")
                chunk.manufacturer = final_meta.get("manufacturer")
                chunk.equipment = final_meta.get("equipment")

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

            # Persist document metadata to the relational database
            page_count = max((c.page_number for c in chunks), default=1)
            if db is not None:
                doc_record = Document(
                    id=document_id,
                    user_id=user_id,
                    filename=safe_filename,
                    stored_path=str(stored_path),
                    page_count=page_count,
                    chunk_count=len(chunks),
                    embedded_count=stored_count,
                    document_type=final_meta.get("document_type"),
                    manufacturer=final_meta.get("manufacturer"),
                    equipment=final_meta.get("equipment"),
                )
                db.add(doc_record)
                await db.commit()
                logger.info("Upload flow: document metadata persisted to database | document_id: %s", document_id)

            logger.info("Upload flow: request completed successfully | document_id: %s", document_id)
            return IngestionResult(
                document_id=document_id,
                filename=safe_filename,
                stored_path=str(stored_path),
                page_count=page_count,
                chunk_count=len(chunks),
                embedded_count=stored_count,
                document_type=final_meta.get("document_type"),
                manufacturer=final_meta.get("manufacturer"),
                equipment=final_meta.get("equipment"),
            )
        except Exception:
            # Clean up the orphaned vectors from Milvus since ingestion failed
            if document_id is not None:
                try:
                    await self.vector_store.delete_document(document_id, user_id)
                    logger.info("Cleaned up orphaned vectors from Milvus due to ingestion failure: %s", document_id)
                except Exception as e:
                    logger.warning("Could not delete orphaned vectors for document %s from Milvus: %s", document_id, e)

            # Clean up the orphaned file since ingestion failed
            if document_id is not None:
                try:
                    file_key = f"{document_id}_{safe_filename}"
                    await self.storage_provider.delete_file(file_key)
                    logger.info("Cleaned up orphaned file due to ingestion failure: %s", file_key)
                except Exception as e:
                    logger.warning("Could not delete orphaned file: %s", e)
            raise

