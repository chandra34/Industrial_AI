import logging
import re
import numpy as np

from pymilvus import AsyncMilvusClient, MilvusException

from backend.config.settings import Settings
from backend.rag.chunking import ChunkRecord

logger = logging.getLogger(__name__)


def sanitize_filter_value(value: str, field_name: str) -> str:
    """Validate that a value is safe to use in a Milvus filter expression.

    Only alphanumeric characters, hyphens, underscores, and dots are allowed.
    Raises ValueError if the value contains unsafe characters that could
    be used for filter/expression injection.
    """
    if not value or not re.fullmatch(r"[A-Za-z0-9._-]+", value):
        raise ValueError(
            f"Invalid {field_name}: contains disallowed characters"
        )
    return value


async def execute_insert_chunks(
    async_client: AsyncMilvusClient,
    collection_name: str,
    settings: Settings,
    chunks: list[ChunkRecord],
    embeddings: np.ndarray,
    user_id: str,
) -> int:
    """Insert chunk embeddings into Milvus for ``user_id`` and return the count inserted.

    Milvus will automatically generate the sparse BM25 vector from ``chunk_text``
    via the native BM25 function if enabled.
    """
    if not chunks:
        return 0
    if len(chunks) != len(embeddings):
        raise ValueError("Chunk count and embedding count must match")

    data = []
    for chunk, emb in zip(chunks, embeddings):
        data.append(
            {
                "document_id": chunk.document_id,
                "user_id": user_id,
                "source_filename": chunk.source_filename,
                "page_number": int(chunk.page_number),
                "chunk_index": int(chunk.chunk_index),
                "chunk_text": chunk.text,
                "embedding": emb.tolist(),
                "document_type": chunk.document_type or "",
                "manufacturer": chunk.manufacturer or "",
                "equipment": chunk.equipment or "",
                "section": chunk.section or "",
            }
        )

    batch_size = settings.milvus_insert_batch_size
    total_inserted = 0
    total_batches = (len(data) + batch_size - 1) // batch_size

    for i in range(0, len(data), batch_size):
        batch = data[i : i + batch_size]
        await async_client.insert(collection_name=collection_name, data=batch)
        total_inserted += len(batch)
        logger.info(
            "Inserted batch %s/%s (%s vectors) into %s for user %s",
            (i // batch_size) + 1,
            total_batches,
            len(batch),
            collection_name,
            user_id,
        )

    try:
        await async_client.flush([collection_name])
    except Exception:
        logger.debug("Flush not required or failed")

    logger.info(
        "Successfully inserted %s total vectors into %s for user %s",
        total_inserted,
        collection_name,
        user_id,
    )
    return total_inserted


async def execute_delete_document(
    async_client: AsyncMilvusClient,
    collection_name: str,
    document_id: str,
    user_id: str,
) -> None:
    """Delete all vectors (dense and sparse) for the specified document_id and user_id.

    Milvus handles sparse index cleanup automatically when rows are deleted.
    """
    if not await async_client.has_collection(collection_name):
        return

    safe_doc_id = sanitize_filter_value(document_id, "document_id")
    safe_user_id = sanitize_filter_value(user_id, "user_id")
    filter_expr = f'document_id == "{safe_doc_id}" and user_id == "{safe_user_id}"'
    try:
        await async_client.delete(
            collection_name=collection_name,
            filter=filter_expr
        )
        try:
            await async_client.flush([collection_name])
        except Exception:
            pass
        logger.info("Deleted document %s for user %s from Milvus", document_id, user_id)
    except MilvusException as exc:
        logger.error("Failed to delete document %s for user %s from Milvus: %s", document_id, user_id, exc)
        raise RuntimeError(f"Failed to delete document from vector store: {exc}") from exc
