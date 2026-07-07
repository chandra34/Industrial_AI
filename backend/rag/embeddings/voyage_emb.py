import logging
from typing import Iterable
import numpy as np
import voyageai
from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_exception

from backend.config.settings import Settings
from backend.rag.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)

def is_voyage_rate_limit(exception: Exception) -> bool:
    """Helper to detect Voyage AI rate limits."""
    try:
        from voyageai.error import RateLimitError
        if isinstance(exception, RateLimitError):
            return True
    except ImportError:
        pass
    class_name = exception.__class__.__name__
    return "RateLimitError" in class_name or "429" in str(exception)

# Shared retry configuration for Voyage
voyage_retry = retry(
    retry=retry_if_exception(is_voyage_rate_limit),
    wait=wait_random_exponential(min=1, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
    before_sleep=lambda retry_state: logger.warning(
        f"Voyage AI rate limit (429) hit. Retrying in {retry_state.next_action.sleep:.2f} seconds... "
        f"Attempt {retry_state.attempt_number}."
    )
)

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

    @voyage_retry
    async def _embed_batch(self, texts: list[str]) -> np.ndarray:
        result = await self.client.embed(
            texts=texts,
            model=self.settings.embedding_model_name,
            input_type="document",
            output_dimension=self.settings.milvus_dimension
        )
        return np.array(result.embeddings, dtype=np.float32)

    @voyage_retry
    async def embed_query(self, query: str) -> np.ndarray:
        """Override to specifically use input_type='query'."""
        result = await self.client.embed(
            texts=[query],
            model=self.settings.embedding_model_name,
            input_type="query",
            output_dimension=self.settings.milvus_dimension
        )
        return np.array(result.embeddings, dtype=np.float32)
