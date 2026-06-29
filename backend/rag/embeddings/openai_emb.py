import logging
import numpy as np
from openai import OpenAI

from backend.config.settings import Settings
from backend.rag.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)

class OpenAIEmbedding(EmbeddingProvider):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        if not settings.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is required. Set it in .env or the environment."
            )
        self.client = OpenAI(api_key=settings.openai_api_key)
        logger.info(
            "Using OpenAI embedding model %s (dim=%s)",
            settings.embedding_model_name,
            settings.milvus_dimension,
        )



    def _embed_batch(self, texts: list[str]) -> np.ndarray:
        # Note: 'dimensions' parameter is only supported by 'text-embedding-3-*' models
        kwargs = {
            "model": self.settings.embedding_model_name,
            "input": texts,
        }
        if self.settings.embedding_model_name.startswith("text-embedding-3"):
            kwargs["dimensions"] = self.settings.milvus_dimension
            
        response = self.client.embeddings.create(**kwargs)
        
        vectors = np.array([x.embedding for x in response.data], dtype=np.float32)
        if vectors.shape[1] != self.settings.milvus_dimension:
            raise ValueError(
                f"Embedding dimension {vectors.shape[1]} does not match "
                f"MILVUS_DIMENSION={self.settings.milvus_dimension}"
            )
        return vectors
