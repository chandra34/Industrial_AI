import logging
import numpy as np
from google import genai
from google.genai import types

from backend.config.settings import Settings
from backend.rag.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)

class GeminiEmbedding(EmbeddingProvider):
    """Google Gemini embedding provider with L2-normalized vectors."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        if not settings.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is required. Set it in .env or the environment."
            )
        self.client = genai.Client(api_key=settings.gemini_api_key)
        logger.info(
            "Using Google embedding model %s (dim=%s)",
            settings.embedding_model_name,
            settings.milvus_dimension,
        )

    def _embed_config(self) -> types.EmbedContentConfig:
        return types.EmbedContentConfig(
            output_dimensionality=self.settings.milvus_dimension,
        )

    @staticmethod
    def _normalize(vectors: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        return (vectors / norms).astype(np.float32)

    async def _embed_batch(self, texts: list[str]) -> np.ndarray:
        result = await self.client.aio.models.embed_content(
            model=self.settings.embedding_model_name,
            contents=texts,
            config=self._embed_config(),
        )
        vectors = np.array([embedding.values for embedding in result.embeddings], dtype=np.float32)
        if vectors.shape[1] != self.settings.milvus_dimension:
            raise ValueError(
                f"Embedding dimension {vectors.shape[1]} does not match "
                f"MILVUS_DIMENSION={self.settings.milvus_dimension}"
            )
        return self._normalize(vectors)
