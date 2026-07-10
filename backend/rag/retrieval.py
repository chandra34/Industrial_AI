from dataclasses import dataclass
import logging
import time


from backend.config.settings import Settings
from backend.rag.embeddings import EmbeddingProvider
from backend.rag.llm import LLMProvider
from backend.services.reranker_service import RerankerService
from backend.vectordb.milvus_db import MilvusStore, VectorSearchHit
from backend.vectordb.filters import build_scalar_filter

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RetrievedChunk:
    document_id: str
    source_filename: str
    page_number: int
    chunk_index: int
    chunk_text: str
    score: float
    document_type: str = ""
    manufacturer: str = ""
    equipment: str = ""
    section: str = ""


class RetrievalService:
    """Hybrid dense + sparse (BM25) retrieval with optional reranking.

    When ``bm25_enabled`` is True, retrieval is performed via Milvus native
    hybrid search (dense + sparse BM25 with RRF fusion inside the database).
    When disabled, only dense vector search is used.
    """

    def __init__(
        self,
        settings: Settings,
        vector_store: MilvusStore,
        embedding_service: EmbeddingProvider,
        reranker_service: RerankerService | None = None,
        llm_service: LLMProvider | None = None,
    ) -> None:
        self.settings = settings
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.reranker_service = reranker_service
        self.llm_service = llm_service

    async def _extract_intent_filter(self, query: str) -> str | None:
        """Extract search intent filters (manufacturer/equipment) from the query using the LLM service."""
        import json
        from pydantic import BaseModel, Field
        import re

        class QueryIntent(BaseModel):
            model_config = {"extra": "forbid"}
            manufacturer: str = Field(description="Extracted equipment manufacturer name or 'Unknown'")
            equipment: str = Field(description="Extracted specific equipment model/name or 'Unknown'")

        if not self.llm_service:
            return None

        try:
            prompt = (
                "Analyze the following user search query or work permit request and extract any referenced "
                "equipment manufacturer or specific equipment name/model.\n\n"
                "CRITICAL: Normalize the 'manufacturer' and 'equipment' values to lowercase, singular form "
                "(e.g. use 'centrifugal pump' instead of 'Centrifugal Pumps', 'boiler' instead of 'Boilers', "
                "'siemens' instead of 'Siemens').\n\n"
                f"Query: {query}"
            )
            messages = [{"role": "user", "content": prompt}]
            content = await self.llm_service.generate_structured_output(
                messages=messages,
                response_model=QueryIntent,
                temperature=0.0
            )
            intent_dict = json.loads(content)

            expr = build_scalar_filter(
                intent_dict.get("manufacturer"),
                intent_dict.get("equipment")
            )
            if expr:
                logger.info("Extracted intent filter: %s", expr)
            return expr
        except Exception as e:
            logger.warning("Failed to extract query intent: %s", e)
            return None

    async def search(
        self,
        query: str,
        user_id: str,
        top_k: int | None = None,
        metadata_filter: str | None = None,
    ) -> list[RetrievedChunk]:
        """Return the top matching chunks for ``query`` scoped to ``user_id`` with dynamic metadata filtering."""
        # Log retrieval start with query preview for data sanitization
        query_preview = (query[:60] + "...") if len(query) > 60 else query
        logger.info("Query flow: retrieval started | query_preview: '%s' | user_id: %s", query_preview, user_id)

        top_k = top_k or self.settings.top_k

        # Extract filters from query if not manually passed
        if not metadata_filter:
            metadata_filter = await self._extract_intent_filter(query)

        if metadata_filter:
            logger.info("Query flow: applying metadata pre-filter: %s", metadata_filter)

        # Determine candidate pool size when reranker is enabled
        if self.settings.reranker_enabled and self.reranker_service:
            candidate_k = self.settings.reranker_candidate_k
        else:
            candidate_k = top_k

        # Generate dense query embedding
        start_embed = time.perf_counter()
        query_embedding = await self.embedding_service.embed_query(query)
        duration_embed = time.perf_counter() - start_embed
        logger.info("Query flow: query embedding generated | duration: %.3fs", duration_embed)

        # Perform search (hybrid or dense-only)
        if self.settings.bm25_enabled:
            start_search = time.perf_counter()
            hits = await self.vector_store.hybrid_search(
                query_embedding=query_embedding,
                query_text=query,
                top_k=candidate_k,
                user_id=user_id,
                metadata_filter=metadata_filter,
            )
            duration_search = time.perf_counter() - start_search
            logger.info(
                "Query flow: hybrid search done (dense + BM25 RRF) | hits: %d | duration: %.3fs",
                len(hits), duration_search,
            )

            # Fallback if filtered search yielded no results
            if not hits and metadata_filter:
                logger.warning(
                    "Query flow: filtered hybrid search returned 0 hits for user %s with filter (%s). "
                    "Falling back to unfiltered search to ensure recall.",
                    user_id, metadata_filter
                )
                start_search = time.perf_counter()
                hits = await self.vector_store.hybrid_search(
                    query_embedding=query_embedding,
                    query_text=query,
                    top_k=candidate_k,
                    user_id=user_id,
                    metadata_filter=None,
                )
                duration_search = time.perf_counter() - start_search
                logger.info(
                    "Query flow: fallback hybrid search done | hits: %d | duration: %.3fs",
                    len(hits), duration_search,
                )
        else:
            start_search = time.perf_counter()
            hits = await self.vector_store.search(
                query_embedding=query_embedding,
                top_k=candidate_k,
                user_id=user_id,
                metadata_filter=metadata_filter,
            )
            duration_search = time.perf_counter() - start_search
            logger.info(
                "Query flow: dense-only search done | hits: %d | duration: %.3fs",
                len(hits), duration_search,
            )

            # Fallback if filtered search yielded no results
            if not hits and metadata_filter:
                logger.warning(
                    "Query flow: filtered dense search returned 0 hits for user %s with filter (%s). "
                    "Falling back to unfiltered search to ensure recall.",
                    user_id, metadata_filter
                )
                start_search = time.perf_counter()
                hits = await self.vector_store.search(
                    query_embedding=query_embedding,
                    top_k=candidate_k,
                    user_id=user_id,
                    metadata_filter=None,
                )
                duration_search = time.perf_counter() - start_search
                logger.info(
                    "Query flow: fallback dense search done | hits: %d | duration: %.3fs",
                    len(hits), duration_search,
                )

        # Convert VectorSearchHit objects to RetrievedChunk objects
        chunks = [_hit_to_chunk(hit) for hit in hits]

        # Apply reranking if enabled
        if self.settings.reranker_enabled and self.reranker_service:
            start_rerank = time.perf_counter()
            chunks = await self.reranker_service.rerank(query, chunks, top_k)
            duration_rerank = time.perf_counter() - start_rerank
            logger.info(
                "Query flow: reranking done | input: %d | output: %d | duration: %.3fs",
                len(hits), len(chunks), duration_rerank,
            )
        else:
            chunks = chunks[:top_k]
            logger.info("Query flow: reranking skipped | output: %d", len(chunks))

        return chunks


def _hit_to_chunk(hit: VectorSearchHit) -> RetrievedChunk:
    return RetrievedChunk(
        document_id=hit.document_id,
        source_filename=hit.source_filename,
        page_number=hit.page_number,
        chunk_index=hit.chunk_index,
        chunk_text=hit.chunk_text,
        score=hit.score,
        document_type=hit.document_type,
        manufacturer=hit.manufacturer,
        equipment=hit.equipment,
        section=hit.section,
    )
