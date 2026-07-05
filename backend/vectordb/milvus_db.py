from dataclasses import dataclass
import logging
from typing import Any

import numpy as np

from backend.config.settings import Settings
from backend.rag.chunking import ChunkRecord

# Import submodules to trigger import-time bootstrapping in client.py
from backend.vectordb.client import (
    create_milvus_client,
    create_async_milvus_client,
    close_clients,
    run_health_check,
)
from backend.vectordb.schema import reconcile_collection_schema
from backend.vectordb.reads import (
    VectorSearchHit,
    execute_dense_search,
    execute_hybrid_search,
)
from backend.vectordb.writes import (
    execute_insert_chunks,
    execute_delete_document,
)

logger = logging.getLogger(__name__)


class MilvusStore:
    """Milvus-backed vector store for document chunk storage and search."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.collection_name = settings.milvus_collection_name
        self._uri = settings.resolved_milvus_uri
        self._client = create_milvus_client(settings)
        self._async_client = create_async_milvus_client(settings)

        # Schema reconciliation: may return updated clients if recreated
        self._client, self._async_client = reconcile_collection_schema(
            self._client,
            self._async_client,
            self.settings,
        )

    async def insert_chunks(self, chunks: list[ChunkRecord], embeddings: np.ndarray, user_id: str) -> int:
        """Insert chunk embeddings into Milvus for ``user_id`` and return the count inserted."""
        return await execute_insert_chunks(
            async_client=self._async_client,
            collection_name=self.collection_name,
            settings=self.settings,
            chunks=chunks,
            embeddings=embeddings,
            user_id=user_id,
        )

    async def search(
        self,
        query_embedding: np.ndarray,
        top_k: int,
        user_id: str,
        metadata_filter: str | None = None,
    ) -> list[VectorSearchHit]:
        """Perform a dense-only vector similarity search scoped to ``user_id``."""
        return await execute_dense_search(
            async_client=self._async_client,
            collection_name=self.collection_name,
            settings=self.settings,
            query_embedding=query_embedding,
            top_k=top_k,
            user_id=user_id,
            metadata_filter=metadata_filter,
        )

    async def hybrid_search(
        self,
        query_embedding: np.ndarray,
        query_text: str,
        top_k: int,
        user_id: str,
        metadata_filter: str | None = None,
    ) -> list[VectorSearchHit]:
        """Perform a hybrid dense + sparse (BM25) search with RRF fusion inside Milvus."""
        return await execute_hybrid_search(
            async_client=self._async_client,
            collection_name=self.collection_name,
            settings=self.settings,
            query_embedding=query_embedding,
            query_text=query_text,
            top_k=top_k,
            user_id=user_id,
            metadata_filter=metadata_filter,
        )

    async def delete_document(self, document_id: str, user_id: str) -> None:
        """Delete all vectors (dense and sparse) for the specified document_id and user_id."""
        await execute_delete_document(
            async_client=self._async_client,
            collection_name=self.collection_name,
            document_id=document_id,
            user_id=user_id,
        )

    async def close(self) -> None:
        """Release database connections."""
        await close_clients(self._client, self._async_client)

    def check_health(self) -> bool:
        """Verify connection to Milvus by checking if list_collections works."""
        return run_health_check(self._client)
