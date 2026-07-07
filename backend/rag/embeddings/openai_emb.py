import logging
import numpy as np
import openai
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_exception

from backend.config.settings import Settings
from backend.rag.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)

class OpenAIEmbedding(EmbeddingProvider):
    """OpenAI embedding provider."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        if not settings.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is required. Set it in .env or the environment."
            )
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        logger.info(
            "Using OpenAI embedding model %s (dim=%s)",
            settings.embedding_model_name,
            settings.milvus_dimension,
        )



    @retry(
        retry=retry_if_exception(lambda e: isinstance(e, openai.RateLimitError)),
        wait=wait_random_exponential(min=1, max=60),
        stop=stop_after_attempt(5),
        reraise=True,
        before_sleep=lambda retry_state: logger.warning(
            f"OpenAI API rate limit (429) hit. Retrying in {retry_state.next_action.sleep:.2f} seconds... "
            f"Attempt {retry_state.attempt_number}."
        )
    )
    async def _embed_batch(self, texts: list[str]) -> np.ndarray:
        # Note: 'dimensions' parameter is only supported by 'text-embedding-3-*' models
        kwargs = {
            "model": self.settings.embedding_model_name,
            "input": texts,
        }
        if self.settings.embedding_model_name.startswith("text-embedding-3"):
            kwargs["dimensions"] = self.settings.milvus_dimension
            
        response = await self.client.embeddings.create(**kwargs)
        
        vectors = np.array([x.embedding for x in response.data], dtype=np.float32)
        if vectors.shape[1] != self.settings.milvus_dimension:
            raise ValueError(
                f"Embedding dimension {vectors.shape[1]} does not match "
                f"MILVUS_DIMENSION={self.settings.milvus_dimension}"
            )
        return vectors
