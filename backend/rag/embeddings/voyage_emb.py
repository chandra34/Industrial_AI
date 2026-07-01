import logging
from typing import Iterable
import numpy as np
import voyageai

from backend.config.settings import Settings
from backend.rag.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)

class VoyageEmbedding(EmbeddingProvider):
    """Voyage AI embedding provider with query/document input types."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        if not settings.voyage_api_key:
            raise ValueError(
                "VOYAGE_API_KEY is required. Set it in .env or the environment."
            )
        self.client = voyageai.AsyncClient(api_key=settings.voyage_api_key)
        logger.info(
            "Using Voyage embedding model %s",
            settings.embedding_model_name,
        )

    async def _embed_batch(self, texts: list[str]) -> np.ndarray:
        # Fallback method if called directly; defaults to None input_type.
        result = await self.client.embed(
            texts=texts,
            model=self.settings.embedding_model_name,
            output_dimension=self.settings.milvus_dimension
        )
        return np.array(result.embeddings, dtype=np.float32)

    async def embed_query(self, query: str) -> np.ndarray:
        """Override to specifically use input_type='query'."""
        result = await self.client.embed(
            texts=[query],
            model=self.settings.embedding_model_name,
            input_type="query",
            output_dimension=self.settings.milvus_dimension
        )
        return np.array(result.embeddings, dtype=np.float32)

    async def embed_texts(self, texts: Iterable[str]) -> np.ndarray:
        """Override to specifically use input_type='document' and handle batching."""
        text_list = list(texts)
        if not text_list:
            return np.empty((0, self.settings.milvus_dimension), dtype=np.float32)

        batch_size = self.settings.embedding_batch_size
        batches: list[np.ndarray] = []
        for start in range(0, len(text_list), batch_size):
            batch = text_list[start : start + batch_size]
            
            result = await self.client.embed(
                texts=batch,
                model=self.settings.embedding_model_name,
                input_type="document",
                output_dimension=self.settings.milvus_dimension
            )
            batches.append(np.array(result.embeddings, dtype=np.float32))
            
        return np.vstack(batches)
