from dataclasses import dataclass
import logging
from typing import Any
import numpy as np

from pymilvus import AsyncMilvusClient, AnnSearchRequest, RRFRanker

from backend.config.settings import Settings
from backend.vectordb.schema import effective_index_type
from backend.vectordb.writes import sanitize_filter_value

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class VectorSearchHit:
    document_id: str
    source_filename: str
    page_number: int
    chunk_index: int
    chunk_text: str
    score: float


_OUTPUT_FIELDS = ["document_id", "source_filename", "page_number", "chunk_index", "chunk_text"]


def parse_search_hit(hit: Any) -> VectorSearchHit:
    """Extract a VectorSearchHit from a pymilvus result object (dict or object)."""
    entity = getattr(hit, "entity", None) or (hit.get("entity") if isinstance(hit, dict) else {})
    score = (
        getattr(hit, "distance", None)
        or getattr(hit, "score", None)
        or (hit.get("distance") if isinstance(hit, dict) else None)
        or (hit.get("score") if isinstance(hit, dict) else None)
    )
    return VectorSearchHit(
        document_id=str(entity.get("document_id")),
        source_filename=str(entity.get("source_filename")),
        page_number=int(entity.get("page_number") or 0),
        chunk_index=int(entity.get("chunk_index") or 0),
        chunk_text=str(entity.get("chunk_text") or ""),
        score=float(score) if score is not None else 0.0,
    )


def dense_search_params(settings: Settings) -> dict[str, Any]:
    """Prepare search parameters for dense search based on index type."""
    params: dict[str, Any] = {"metric_type": settings.milvus_metric_type}
    index_type = effective_index_type(settings)
    if index_type == "HNSW":
        params["params"] = {"ef": settings.milvus_ef_search}
    elif index_type.startswith("IVF"):
        params["params"] = {"nprobe": settings.milvus_nprobe}
    return params


async def execute_dense_search(
    async_client: AsyncMilvusClient,
    collection_name: str,
    settings: Settings,
    query_embedding: np.ndarray,
    top_k: int,
    user_id: str,
) -> list[VectorSearchHit]:
    """Perform a dense-only vector similarity search scoped to ``user_id``."""
    if query_embedding.ndim == 1:
        query_embedding = np.expand_dims(query_embedding, axis=0)

    results = await async_client.search(
        collection_name=collection_name,
        data=query_embedding.tolist(),
        limit=top_k,
        filter=f'user_id == "{sanitize_filter_value(user_id, "user_id")}"',
        search_params=dense_search_params(settings),
        output_fields=_OUTPUT_FIELDS,
    )

    hits: list[VectorSearchHit] = []
    for batch in results:
        for hit in batch:
            hits.append(parse_search_hit(hit))

    return hits


async def execute_hybrid_search(
    async_client: AsyncMilvusClient,
    collection_name: str,
    settings: Settings,
    query_embedding: np.ndarray,
    query_text: str,
    top_k: int,
    user_id: str,
) -> list[VectorSearchHit]:
    """Perform a hybrid dense + sparse (BM25) search with RRF fusion inside Milvus.

    Milvus executes both search requests server-side and merges results
    using Reciprocal Rank Fusion before returning a unified result set.
    """
    if query_embedding.ndim == 1:
        query_embedding_list = query_embedding.tolist()
    else:
        query_embedding_list = query_embedding[0].tolist()

    safe_user_id = sanitize_filter_value(user_id, "user_id")
    filter_expr = f'user_id == "{safe_user_id}"'

    # Dense ANN search request
    dense_req = AnnSearchRequest(
        data=[query_embedding_list],
        anns_field="embedding",
        param=dense_search_params(settings),
        limit=top_k,
        expr=filter_expr,
    )

    # Sparse BM25 search request — pass raw query text; Milvus tokenizes it
    sparse_req = AnnSearchRequest(
        data=[query_text],
        anns_field="sparse_vector",
        param={"metric_type": "BM25"},
        limit=top_k,
        expr=filter_expr,
    )

    results = await async_client.hybrid_search(
        collection_name=collection_name,
        reqs=[dense_req, sparse_req],
        ranker=RRFRanker(),
        limit=top_k,
        output_fields=_OUTPUT_FIELDS,
    )

    hits: list[VectorSearchHit] = []
    for hit in results[0]:
        hits.append(parse_search_hit(hit))

    return hits
