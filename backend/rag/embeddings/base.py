from abc import ABC, abstractmethod
from typing import Iterable
import asyncio
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
        batches = [
            text_list[start : start + batch_size]
            for start in range(0, len(text_list), batch_size)
        ]

        sem = asyncio.Semaphore(self.settings.embedding_concurrency)

        async def _embed_with_sem(batch: list[str]) -> np.ndarray:
            async with sem:
                return await self._embed_batch(batch)

        tasks = [_embed_with_sem(b) for b in batches]
        embedded_batches = await asyncio.gather(*tasks)
        return np.vstack(embedded_batches)

    async def embed_query(self, query: str) -> np.ndarray:
        """Embed a single query string asynchronously."""
        return await self._embed_batch([query])
