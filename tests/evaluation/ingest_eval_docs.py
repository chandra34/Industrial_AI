"""
One-time ingestion of evaluation PDF documents into an isolated Milvus collection.

This module copies the 5 evaluation PDFs from the local source directory into
the workspace, then parses, embeds, and indexes them into `eval_collection`.
If the collection is already populated, ingestion is skipped entirely.
"""

import asyncio
import logging
import shutil
from pathlib import Path

from backend.config.settings import get_settings, Settings
from backend.rag.embeddings import EmbeddingFactory
from backend.rag.llm import LLMFactory
from backend.services.ingest_service import IngestService
from backend.services.storage import LocalStorageProvider
from backend.vectordb.milvus_db import MilvusStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EVAL_PDFS_SOURCE = Path(r"C:\Users\chand\Downloads\RAG_evalution")
EVAL_PDFS_DEST = Path(__file__).resolve().parent / "documents"
EVAL_USER_ID = "eval-user"
EVAL_COLLECTION = "eval_collection"

EXPECTED_PDFS = [
    "Math.pdf",
    "Tender_Document.pdf",
    "steam_boiler_sop.pdf",
    "power_plant_sop.pdf",
    "lab_report.pdf",
]


def get_eval_settings() -> Settings:
    """Return a Settings instance with the collection overridden for evaluation."""
    settings = get_settings()
    settings.milvus_collection_name = EVAL_COLLECTION
    # Disable reranker and BM25 for deterministic retrieval evaluation
    settings.reranker_enabled = False
    settings.bm25_enabled = False
    return settings


def _copy_pdfs_to_workspace() -> None:
    """Copy evaluation PDFs from the local source into the workspace directory."""
    EVAL_PDFS_DEST.mkdir(parents=True, exist_ok=True)
    for pdf_name in EXPECTED_PDFS:
        src = EVAL_PDFS_SOURCE / pdf_name
        dst = EVAL_PDFS_DEST / pdf_name
        if not dst.exists():
            if not src.exists():
                raise FileNotFoundError(
                    f"Evaluation PDF not found at source: {src}. "
                    f"Please ensure all 5 evaluation PDFs exist in {EVAL_PDFS_SOURCE}"
                )
            shutil.copy2(src, dst)
            logger.info("Copied evaluation PDF: %s -> %s", src, dst)
        else:
            logger.info("Evaluation PDF already exists: %s", dst)


def _collection_is_populated(vector_store: MilvusStore) -> bool:
    """Check whether the evaluation collection already has indexed documents."""
    try:
        collection_name = vector_store.collection_name
        if not vector_store._client.has_collection(collection_name):
            return False
        # Query for a small sample to check if data exists
        results = vector_store._client.query(
            collection_name=collection_name,
            filter=f'user_id == "{EVAL_USER_ID}"',
            output_fields=["document_id"],
            limit=1,
        )
        return len(results) > 0
    except Exception as e:
        logger.warning("Failed to check if eval collection is populated: %s", e)
        return False


async def ingest_eval_documents(settings: Settings | None = None) -> MilvusStore:
    """Copy evaluation PDFs, ingest into eval_collection, and return the vector store.

    If the collection is already populated, ingestion is skipped.
    """
    if settings is None:
        settings = get_eval_settings()

    _copy_pdfs_to_workspace()

    vector_store = MilvusStore(settings)

    if _collection_is_populated(vector_store):
        logger.info(
            "Eval collection '%s' is already populated. Skipping ingestion.",
            EVAL_COLLECTION,
        )
        return vector_store

    logger.info("Ingesting %d evaluation PDFs into '%s'...", len(EXPECTED_PDFS), EVAL_COLLECTION)

    embedding_service = EmbeddingFactory.create(settings)
    llm_service = LLMFactory.create(settings)
    storage_provider = LocalStorageProvider(settings)
    ingest_service = IngestService(
        settings, vector_store, embedding_service, llm_service, storage_provider,
    )

    total_chunks = 0
    total_embedded = 0
    total_stored = 0
    ingestion_issues: list[str] = []

    for i, pdf_name in enumerate(EXPECTED_PDFS):
        pdf_path = EVAL_PDFS_DEST / pdf_name
        pdf_bytes = pdf_path.read_bytes()
        logger.info("=" * 60)
        logger.info("[INGEST] Starting: %s (%d bytes)", pdf_name, len(pdf_bytes))

        result = await ingest_service.ingest_pdf(
            file_bytes=pdf_bytes,
            original_name=pdf_name,
            user_id=EVAL_USER_ID,
            db=None,  # Skip SQL persistence to avoid polluting production database
        )

        # ---------------------------------------------------------------
        # Verification: compare parsed chunks vs embeddings vs Milvus rows
        # ---------------------------------------------------------------
        chunk_count = result.chunk_count
        embedded_count = result.embedded_count
        stored_count = embedded_count  # stored_count == embedded_count in IngestionResult

        total_chunks += chunk_count
        total_embedded += embedded_count
        total_stored += stored_count

        logger.info("[INGEST] ✅ Parsed chunks  : %d", chunk_count)
        logger.info("[INGEST] ✅ Embeddings made: %d", embedded_count)
        logger.info("[INGEST] ✅ Vectors stored : %d", stored_count)

        # Detect rate-limit or partial embedding failures
        if embedded_count < chunk_count:
            msg = (
                f"[INGEST] ⚠️  RATE LIMIT / EMBEDDING GAP detected for '{pdf_name}': "
                f"{chunk_count - embedded_count} chunks did NOT get embeddings "
                f"({embedded_count}/{chunk_count})"
            )
            logger.warning(msg)
            ingestion_issues.append(msg)
        else:
            logger.info("[INGEST] ✅ All %d chunks got embeddings (no rate limit issue)", chunk_count)

        if stored_count < embedded_count:
            msg = (
                f"[INGEST] ⚠️  MILVUS INSERT GAP detected for '{pdf_name}': "
                f"{embedded_count - stored_count} embeddings were NOT indexed "
                f"({stored_count}/{embedded_count})"
            )
            logger.warning(msg)
            ingestion_issues.append(msg)
        else:
            logger.info("[INGEST] ✅ All %d embeddings were indexed into Milvus", stored_count)

        # Live Milvus count verification — query actual rows for this document
        try:
            live_rows = vector_store._client.query(
                collection_name=EVAL_COLLECTION,
                filter=f'document_id == "{result.document_id}"',
                output_fields=["chunk_index"],
                limit=16384,
            )
            live_count = len(live_rows)
            logger.info(
                "[INGEST] ✅ Live Milvus row count for document_id '%s': %d (expected %d)",
                result.document_id, live_count, stored_count,
            )
            if live_count != stored_count:
                msg = (
                    f"[INGEST] ⚠️  MILVUS LIVE COUNT MISMATCH for '{pdf_name}': "
                    f"IngestService reported {stored_count} but Milvus has {live_count} rows"
                )
                logger.warning(msg)
                ingestion_issues.append(msg)
        except Exception as e:
            logger.warning("[INGEST] Could not query live Milvus count for %s: %s", pdf_name, e)

        # Wait between PDFs to let Gemini API quota recover
        if i < len(EXPECTED_PDFS) - 1:
            logger.info("[INGEST] Waiting 60 seconds before next PDF to avoid Gemini rate limits...")
            await asyncio.sleep(60)
            logger.info("[INGEST] Wait complete. Proceeding to next PDF.")

    # Final summary across all 5 PDFs
    # ---------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("[INGEST SUMMARY] PDFs processed        : %d", len(EXPECTED_PDFS))
    logger.info("[INGEST SUMMARY] Total chunks parsed   : %d", total_chunks)
    logger.info("[INGEST SUMMARY] Total embeddings made : %d", total_embedded)
    logger.info("[INGEST SUMMARY] Total vectors stored  : %d", total_stored)

    # Final live total count from Milvus for all eval-user documents
    try:
        all_rows = vector_store._client.query(
            collection_name=EVAL_COLLECTION,
            filter=f'user_id == "{EVAL_USER_ID}"',
            output_fields=["document_id"],
            limit=16384,
        )
        logger.info(
            "[INGEST SUMMARY] ✅ LIVE Milvus total rows for user '%s': %d (expected %d)",
            EVAL_USER_ID, len(all_rows), total_stored,
        )
    except Exception as e:
        logger.warning("[INGEST SUMMARY] Could not query total live Milvus count: %s", e)

    if ingestion_issues:
        logger.error("[INGEST SUMMARY] ❌ %d issue(s) detected during ingestion:", len(ingestion_issues))
        for issue in ingestion_issues:
            logger.error("   %s", issue)
    else:
        logger.info("[INGEST SUMMARY] ✅ No issues detected. All chunks embedded and indexed successfully.")

    logger.info("=" * 60)
    logger.info("Evaluation ingestion complete.")
    return vector_store

