from collections import defaultdict
from dataclasses import dataclass
import logging

from fastapi.concurrency import run_in_threadpool

from backend.config.settings import Settings
from backend.rag.embeddings import EmbeddingProvider
from backend.services.bm25_service import BM25Service
from backend.services.reranker_service import RerankerService
from backend.vectordb.milvus_db import MilvusStore, VectorSearchHit

logger = logging.getLogger(__name__)

# RRF smoothing constant (conventionally 60)
K_RRF = 60


@dataclass(slots=True)
class RetrievedChunk:
    document_id: str
    source_filename: str
    page_number: int
    chunk_index: int
    chunk_text: str
    score: float


def reciprocal_rank_fusion(
    rankings: list[list[str]], k: int = K_RRF
) -> list[tuple[str, float]]:
    """Fuse multiple ranked lists of identifiers (chunk_texts) into one ranked list."""
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for rank, item_id in enumerate(ranking, start=1):
            scores[item_id] += 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda x: -x[1])


class RetrievalService:
    def __init__(
        self,
        settings: Settings,
        vector_store: MilvusStore,
        embedding_service: EmbeddingProvider,
        bm25_service: BM25Service | None = None,
        reranker_service: RerankerService | None = None,
    ) -> None:
        self.settings = settings
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.bm25_service = bm25_service
        self.reranker_service = reranker_service

    async def search(self, query: str, user_id: str, top_k: int | None = None) -> list[RetrievedChunk]:
        top_k = top_k or self.settings.top_k
        
        # Determine candidate pool size for hybrid fusion
        if self.settings.reranker_enabled and self.reranker_service:
            candidate_k = self.settings.reranker_candidate_k
        else:
            candidate_k = max(20, top_k * 3)

        # 1. Fetch dense results
        query_embedding = await run_in_threadpool(self.embedding_service.embed_query, query)
        dense_hits = await self.vector_store.search(query_embedding, candidate_k, user_id)

        # If BM25 is disabled or service is not active, return dense hits (truncated or reranked)
        if not self.settings.bm25_enabled or not self.bm25_service:
            chunks = [_hit_to_chunk(hit) for hit in dense_hits]
            if self.settings.reranker_enabled and self.reranker_service:
                return await self.reranker_service.rerank(query, chunks, top_k)
            return chunks[:top_k]

        # 2. Fetch sparse BM25 results
        try:
            sparse_hits = await run_in_threadpool(self.bm25_service.search, user_id, query, candidate_k)
        except Exception as exc:
            logger.error("BM25 search failed, falling back to dense-only: %s", exc)
            chunks = [_hit_to_chunk(hit) for hit in dense_hits]
            if self.settings.reranker_enabled and self.reranker_service:
                return await self.reranker_service.rerank(query, chunks, top_k)
            return chunks[:top_k]

        # 3. Perform RRF fusion
        dense_texts = [hit.chunk_text for hit in dense_hits]
        sparse_texts = [hit.chunk_text for hit in sparse_hits]

        fused_rankings = reciprocal_rank_fusion([dense_texts, sparse_texts])
        
        fusion_limit = candidate_k if (self.settings.reranker_enabled and self.reranker_service) else top_k
        top_fused = fused_rankings[:fusion_limit]

        # 4. Resolve metadata for fused chunks
        dense_map = {hit.chunk_text: hit for hit in dense_hits}
        
        # Check which fused chunks came exclusively from BM25 and lack metadata
        missing_texts = [text for text, _ in top_fused if text not in dense_map]
        
        missing_map = {}
        if missing_texts:
            try:
                missing_hits = await self.vector_store.get_chunks_by_text(missing_texts, user_id)
                missing_map = {hit.chunk_text: hit for hit in missing_hits}
            except Exception as exc:
                logger.error("Failed to query missing chunk metadata from Milvus: %s", exc)

        # Build the final list of RetrievedChunk objects
        chunks: list[RetrievedChunk] = []
        for chunk_text, score in top_fused:
            hit = dense_map.get(chunk_text) or missing_map.get(chunk_text)
            if hit:
                chunks.append(
                    RetrievedChunk(
                        document_id=hit.document_id,
                        source_filename=hit.source_filename,
                        page_number=hit.page_number,
                        chunk_index=hit.chunk_index,
                        chunk_text=hit.chunk_text,
                        score=score,
                    )
                )
            else:
                # Fallback in the rare case that a BM25 hit has no record in Milvus
                logger.warning("Fused chunk text not found in Milvus metadata: %s", chunk_text[:50])
                chunks.append(
                    RetrievedChunk(
                        document_id="",
                        source_filename="Unknown (Sparse)",
                        page_number=0,
                        chunk_index=-1,
                        chunk_text=chunk_text,
                        score=score,
                    )
                )

        # 5. Apply Reranking if enabled
        if self.settings.reranker_enabled and self.reranker_service:
            chunks = await self.reranker_service.rerank(query, chunks, top_k)

        return chunks


def _hit_to_chunk(hit: VectorSearchHit) -> RetrievedChunk:
    return RetrievedChunk(
        document_id=hit.document_id,
        source_filename=hit.source_filename,
        page_number=hit.page_number,
        chunk_index=hit.chunk_index,
        chunk_text=hit.chunk_text,
        score=hit.score,
    )
