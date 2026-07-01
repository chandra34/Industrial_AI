from abc import ABC, abstractmethod
from typing import Iterable
import numpy as np

from backend.config.settings import Settings

class EmbeddingProvider(ABC):
    """Abstract base class for text embedding providers."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abstractmethod
    async def _embed_batch(self, texts: list[str]) -> np.ndarray:
        """Embed a single batch of texts asynchronously."""
        pass

    async def embed_texts(self, texts: Iterable[str]) -> np.ndarray:
        """Embed an arbitrary number of texts asynchronously, handling batching automatically."""
        text_list = list(texts)
        if not text_list:
            return np.empty((0, self.settings.milvus_dimension), dtype=np.float32)

        batch_size = self.settings.embedding_batch_size
        batches: list[np.ndarray] = []
        for start in range(0, len(text_list), batch_size):
            batch = text_list[start : start + batch_size]
            batches.append(await self._embed_batch(batch))
        return np.vstack(batches)

    async def embed_query(self, query: str) -> np.ndarray:
        """Embed a single query string asynchronously."""
        return await self._embed_batch([query])
