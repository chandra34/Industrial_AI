from __future__ import annotations
import logging
from typing import TYPE_CHECKING

from backend.config.settings import Settings
from backend.services.hf_reranker import HuggingFaceReranker
from backend.services.voyage_reranker import VoyageReranker

if TYPE_CHECKING:
    from backend.rag.retrieval import RetrievedChunk

logger = logging.getLogger(__name__)


class RerankerService:
    """Facade that routes to the configured reranker provider implementation.

    Supported providers (controlled via ``RERANKER_PROVIDER`` env var):
    - ``huggingface`` – Hugging Face Serverless Inference cross-encoder.
    - ``voyage``      – Voyage AI reranker API.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        provider_name = settings.reranker_provider.lower().strip()

        if provider_name == "huggingface":
            self.provider = HuggingFaceReranker(settings)
        elif provider_name == "voyage":
            self.provider = VoyageReranker(settings)
        else:
            raise ValueError(f"Unknown reranker provider: {provider_name}")

    async def rerank(self, query: str, chunks: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        """Score and reorder ``chunks`` using the active provider backend."""
        if not self.settings.reranker_enabled or not chunks:
            return chunks[:top_k]

        return await self.provider.rerank(query, chunks, top_k)

    async def close(self) -> None:
        """Release underlying provider resources."""
        await self.provider.close()
