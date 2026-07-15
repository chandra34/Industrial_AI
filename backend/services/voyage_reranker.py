from __future__ import annotations
import logging
from typing import TYPE_CHECKING
import voyageai
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from backend.config.settings import Settings

if TYPE_CHECKING:
    from backend.rag.retrieval import RetrievedChunk

logger = logging.getLogger(__name__)


def _is_voyage_rate_limit(exception: Exception) -> bool:
    """Helper to detect Voyage AI rate limits."""
    try:
        from voyageai.error import RateLimitError
        return isinstance(exception, RateLimitError)
    except ImportError:
        return False


_voyage_retry = retry(
    retry=retry_if_exception(_is_voyage_rate_limit),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),
    before_sleep=lambda retry_state: logger.warning(
        "Voyage AI rate limit (429) hit. Retrying in %.2f seconds... Attempt %d.",
        retry_state.next_action.sleep,
        retry_state.attempt_number,
    ),
    reraise=True,
)


class VoyageReranker:
    """Rerank retrieval candidates using the Voyage AI API."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model_name = settings.reranker_model_name

        if not settings.voyage_api_key:
            raise ValueError("VOYAGE_API_KEY is required for the Voyage reranker.")

        self.client = voyageai.AsyncClient(api_key=settings.voyage_api_key)
        logger.info("Initialized VoyageReranker with model %s", self.model_name)

    @_voyage_retry
    async def _call_api(self, query: str, documents: list[str], top_k: int) -> voyageai.RerankingObject:
        """Call the Voyage AI rerank API asynchronously with retries."""
        return await self.client.rerank(
            query=query,
            documents=documents,
            model=self.model_name,
            top_k=top_k,
        )

    async def rerank(self, query: str, chunks: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        """Score and reorder ``chunks`` by relevance to ``query`` using Voyage AI."""
        if not chunks:
            return chunks[:top_k]

        documents = [chunk.chunk_text for chunk in chunks]

        try:
            response = await self._call_api(query, documents, top_k)

            # Map relevance scores back to their respective chunks
            for res in response.results:
                chunks[res.index].score = res.relevance_score

            # Sort descending by score
            chunks.sort(key=lambda x: -x.score)

        except Exception as exc:
            logger.error("Voyage Reranking failed: %s. Returning raw candidates.", exc)

        return chunks[:top_k]

    async def close(self) -> None:
        """Lifecycle method (no-op for Voyage AsyncClient as it manages session internally)."""
        pass
