from dataclasses import dataclass
import logging
import os
import re
from typing import Any, Optional

import numpy as np

from backend.config.settings import Settings, get_settings
from backend.rag.chunking import ChunkRecord

logger = logging.getLogger(__name__)


# pymilvus validates os.environ["MILVUS_URI"] at import time (http(s) only).
# Never set MILVUS_URI to a .db path before "from pymilvus import ...".
# The real .db path is passed to MilvusClient(...) only when the store is created.
_IMPORT_PLACEHOLDER_URI = "http://127.0.0.1:19530"


def _bootstrap_pymilvus_environment(settings: Settings) -> str:
    """
    Load Milvus Lite and satisfy pymilvus import-time URI checks.

    For .db URIs: import milvus_lite, set a temporary http MILVUS_URI for import only,
    then pass the resolved .db path to MilvusClient(db_path) in _create_client().
    """
    uri = settings.resolved_milvus_uri
    if settings.uses_milvus_lite:
        try:
            import milvus_lite  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "Milvus Lite is required when MILVUS_URI ends with .db. Install with: "
                'pip install "pymilvus[milvus-lite]>=3.0.0" milvus-lite'
            ) from exc
        os.environ["MILVUS_URI"] = _IMPORT_PLACEHOLDER_URI
        logger.debug("Milvus Lite client URI: %s", uri)
    else:
        os.environ["MILVUS_URI"] = uri
    return uri


_bootstrap_pymilvus_environment(get_settings())

from pymilvus import (  # noqa: E402
    DataType,
    MilvusClient,
    MilvusException,
    AsyncMilvusClient,
    Function,
    FunctionType,
    AnnSearchRequest,
    RRFRanker,
)


@dataclass(slots=True)
class VectorSearchHit:
    document_id: str
    source_filename: str
    page_number: int
    chunk_index: int
    chunk_text: str
    score: float


def _sanitize_filter_value(value: str, field_name: str) -> str:
    """Validate that a value is safe to use in a Milvus filter expression.

    Only alphanumeric characters, hyphens, underscores, and dots are allowed.
    Raises ValueError if the value contains unsafe characters that could
    be used for filter/expression injection.
    """
    if not value or not re.fullmatch(r"[A-Za-z0-9._-]+", value):
        raise ValueError(
            f"Invalid {field_name}: contains disallowed characters"
        )
    return value


# ---------------------------------------------------------------------------
# Output field list shared by search and hybrid_search
# ---------------------------------------------------------------------------
_OUTPUT_FIELDS = ["document_id", "source_filename", "page_number", "chunk_index", "chunk_text"]


def _parse_search_hit(hit: Any) -> VectorSearchHit:
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


class MilvusStore:
    """Milvus-backed vector store for document chunk storage and search."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.collection_name = settings.milvus_collection_name
        self._uri = settings.resolved_milvus_uri
        self._client = self._create_client()
        self._async_client = self._create_async_client()
        self._ensure_collection()

    def _effective_index_type(self) -> str:
        # Milvus Lite only supports FLAT (README); remote Milvus can use HNSW etc.
        if self.settings.uses_milvus_lite:
            return "FLAT"
        return self.settings.milvus_index_type.upper()

    def _create_client(self) -> MilvusClient:
        token: Optional[str] = getattr(self.settings, "milvus_token", None)
        logger.info(
            "Connecting to Milvus at %s (lite=%s)",
            self._uri,
            self.settings.uses_milvus_lite,
        )
        try:
            # Milvus Lite: local file path (official API: MilvusClient("./file.db"))
            if self.settings.uses_milvus_lite:
                return MilvusClient(self._uri)

            # Remote Milvus server
            if token:
                return MilvusClient(uri=self._uri, token=token)
            return MilvusClient(uri=self._uri)
        except MilvusException as exc:
            hint = ""
            if "19530" in str(exc):
                hint = (
                    " No Milvus server is running on localhost:19530. "
                    "For embedded storage, set MILVUS_URI to an absolute path ending in .db "
                    "(e.g. MILVUS_URI=./milvus_local.db) and install milvus-lite."
                )
            raise RuntimeError(f"Failed to connect to Milvus at {self._uri}.{hint}") from exc

    def _create_async_client(self) -> AsyncMilvusClient:
        token: Optional[str] = getattr(self.settings, "milvus_token", None)
        try:
            if self.settings.uses_milvus_lite:
                return AsyncMilvusClient(self._uri)
            if token:
                return AsyncMilvusClient(uri=self._uri, token=token)
            return AsyncMilvusClient(uri=self._uri)
        except MilvusException as exc:
            raise RuntimeError(f"Failed to connect to AsyncMilvusClient at {self._uri}") from exc

    def _build_index_params(self):
        index_params = self._client.prepare_index_params()
        index_type = self._effective_index_type()

        # Dense vector index on 'embedding' field
        dense_kwargs: dict[str, Any] = {
            "field_name": "embedding",
            "index_type": index_type,
            "metric_type": self.settings.milvus_metric_type,
        }
        if index_type == "HNSW":
            dense_kwargs["params"] = {
                "M": self.settings.milvus_m,
                "efConstruction": self.settings.milvus_ef_construction,
            }
        elif index_type.startswith("IVF"):
            dense_kwargs["params"] = {
                "nlist": self.settings.milvus_nlist,
            }
        index_params.add_index(**dense_kwargs)

        # Sparse vector index on 'sparse_vector' field (Milvus native BM25)
        if self.settings.bm25_enabled:
            index_params.add_index(
                field_name="sparse_vector",
                index_type="SPARSE_INVERTED_INDEX",
                metric_type="BM25",
            )

        return index_params

    def _dense_search_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {"metric_type": self.settings.milvus_metric_type}
        index_type = self._effective_index_type()
        if index_type == "HNSW":
            params["params"] = {"ef": self.settings.milvus_ef_search}
        elif index_type.startswith("IVF"):
            params["params"] = {"nprobe": self.settings.milvus_nprobe}
        return params

    def _ensure_collection(self) -> None:
        try:
            if self._client.has_collection(self.collection_name):
                try:
                    desc = self._client.describe_collection(self.collection_name)
                    # Handle both dictionary and object formats for pymilvus versions compatibility
                    fields = desc.get("fields", []) if isinstance(desc, dict) else getattr(desc, "fields", [])
                    field_names = set()
                    user_id_field = None
                    for f in fields:
                        name = f.get("name") if isinstance(f, dict) else getattr(f, "name", None)
                        if name:
                            field_names.add(name)
                        if name == "user_id":
                            user_id_field = f

                    has_user_id = "user_id" in field_names
                    has_sparse = "sparse_vector" in field_names
                    is_part_key = False
                    if user_id_field:
                        is_part_key = user_id_field.get("is_partition_key", False) if isinstance(user_id_field, dict) else getattr(user_id_field, "is_partition_key", False)

                    needs_recreate = (not has_user_id or not is_part_key)
                    # Also recreate if BM25 is enabled but the sparse_vector field is missing
                    if self.settings.bm25_enabled and not has_sparse:
                        needs_recreate = True

                    if needs_recreate:
                        if not self.settings.uses_milvus_lite:
                            logger.error(
                                "Critical: Existing Milvus collection '%s' has schema mismatch "
                                "(missing 'user_id' partition key or 'sparse_vector' field) in production. "
                                "Halt startup to prevent data loss.",
                                self.collection_name,
                            )
                            raise RuntimeError(
                                f"Database schema mismatch: Collection '{self.collection_name}' exists "
                                f"but is missing required fields/configuration. "
                                f"Automatic deletion is blocked in production to protect data. "
                                f"Manual migration required."
                            )

                        logger.warning("Existing collection %s needs schema update. Re-creating.", self.collection_name)
                        try:
                            self._client.drop_collection(self.collection_name)
                        except Exception as drop_exc:
                            logger.warning(
                                "Failed to drop collection %s via client (common Milvus Lite Windows bug): %s. "
                                "Attempting to manually delete collection directory.",
                                self.collection_name, drop_exc
                            )
                            try:
                                self._client.close()
                                self._async_client.close()
                            except Exception:
                                pass

                            from pathlib import Path
                            import shutil
                            coll_dir = Path(self._uri) / "collections" / self.collection_name
                            if coll_dir.exists():
                                shutil.rmtree(coll_dir, ignore_errors=True)

                            # Re-initialize connections
                            self._client = self._create_client()
                            self._async_client = self._create_async_client()
                    else:
                        self._client.load_collection(self.collection_name)
                        return
                except Exception as exc:
                    logger.exception("Failed to check or load existing collection %s: %s", self.collection_name, exc)
                    raise

            index_type = self._effective_index_type()
            logger.info(
                "Creating Milvus collection %s (index=%s, bm25=%s, lite=%s)",
                self.collection_name,
                index_type,
                self.settings.bm25_enabled,
                self.settings.uses_milvus_lite,
            )

            schema = self._client.create_schema(auto_id=True, enable_dynamic_field=False)
            schema.add_field("id", DataType.INT64, is_primary=True)
            schema.add_field("document_id", DataType.VARCHAR, max_length=64)
            schema.add_field("user_id", DataType.VARCHAR, max_length=64, is_partition_key=True)
            schema.add_field("source_filename", DataType.VARCHAR, max_length=512)
            schema.add_field("page_number", DataType.INT64)
            schema.add_field("chunk_index", DataType.INT64)
            schema.add_field(
                "chunk_text", DataType.VARCHAR, max_length=65535,
                enable_analyzer=True,  # Required for Milvus native BM25 tokenization
            )
            schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=self.settings.milvus_dimension)

            # Add sparse vector field and BM25 function if enabled
            if self.settings.bm25_enabled:
                schema.add_field("sparse_vector", DataType.SPARSE_FLOAT_VECTOR)
                bm25_function = Function(
                    name="text_bm25",
                    input_field_names=["chunk_text"],
                    output_field_names=["sparse_vector"],
                    function_type=FunctionType.BM25,
                )
                schema.add_function(bm25_function)
                logger.info("Added BM25 function: chunk_text -> sparse_vector")

            self._client.create_collection(
                collection_name=self.collection_name,
                schema=schema,
                index_params=self._build_index_params(),
            )

            try:
                self._client.create_index(collection_name=self.collection_name, field_name="embedding")
            except Exception:
                logger.debug("create_index not required or failed; continuing")

            self._client.load_collection(self.collection_name)

        except MilvusException as exc:
            logger.exception("Milvus operation failed: %s", exc)
            raise

    async def insert_chunks(self, chunks: list[ChunkRecord], embeddings: np.ndarray, user_id: str) -> int:
        """Insert chunk embeddings into Milvus for ``user_id`` and return the count inserted.

        Milvus will automatically generate the sparse BM25 vector from ``chunk_text``
        via the native BM25 function if enabled.
        """
        if not chunks:
            return 0
        if len(chunks) != len(embeddings):
            raise ValueError("Chunk count and embedding count must match")

        data = []
        for chunk, emb in zip(chunks, embeddings):
            data.append(
                {
                    "document_id": chunk.document_id,
                    "user_id": user_id,
                    "source_filename": chunk.source_filename,
                    "page_number": int(chunk.page_number),
                    "chunk_index": int(chunk.chunk_index),
                    "chunk_text": chunk.text,
                    "embedding": emb.tolist(),
                }
            )

        batch_size = self.settings.milvus_insert_batch_size
        total_inserted = 0
        total_batches = (len(data) + batch_size - 1) // batch_size

        for i in range(0, len(data), batch_size):
            batch = data[i : i + batch_size]
            await self._async_client.insert(collection_name=self.collection_name, data=batch)
            total_inserted += len(batch)
            logger.info(
                "Inserted batch %s/%s (%s vectors) into %s for user %s",
                (i // batch_size) + 1,
                total_batches,
                len(batch),
                self.collection_name,
                user_id,
            )

        try:
            await self._async_client.flush([self.collection_name])
        except Exception:
            logger.debug("Flush not required or failed")

        logger.info(
            "Successfully inserted %s total vectors into %s for user %s",
            total_inserted,
            self.collection_name,
            user_id,
        )
        return total_inserted

    async def search(self, query_embedding: np.ndarray, top_k: int, user_id: str) -> list[VectorSearchHit]:
        """Perform a dense-only vector similarity search scoped to ``user_id``."""
        if query_embedding.ndim == 1:
            query_embedding = np.expand_dims(query_embedding, axis=0)

        results = await self._async_client.search(
            collection_name=self.collection_name,
            data=query_embedding.tolist(),
            limit=top_k,
            filter=f'user_id == "{_sanitize_filter_value(user_id, "user_id")}"',
            search_params=self._dense_search_params(),
            output_fields=_OUTPUT_FIELDS,
        )

        hits: list[VectorSearchHit] = []
        for batch in results:
            for hit in batch:
                hits.append(_parse_search_hit(hit))

        return hits

    async def hybrid_search(
        self,
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

        safe_user_id = _sanitize_filter_value(user_id, "user_id")
        filter_expr = f'user_id == "{safe_user_id}"'

        # Dense ANN search request
        dense_req = AnnSearchRequest(
            data=[query_embedding_list],
            anns_field="embedding",
            param=self._dense_search_params(),
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

        results = await self._async_client.hybrid_search(
            collection_name=self.collection_name,
            reqs=[dense_req, sparse_req],
            ranker=RRFRanker(),
            limit=top_k,
            output_fields=_OUTPUT_FIELDS,
        )

        hits: list[VectorSearchHit] = []
        for hit in results[0]:
            hits.append(_parse_search_hit(hit))

        return hits

    async def delete_document(self, document_id: str, user_id: str) -> None:
        """Delete all vectors (dense and sparse) for the specified document_id and user_id.

        Milvus handles sparse index cleanup automatically when rows are deleted.
        """
        if not await self._async_client.has_collection(self.collection_name):
            return

        safe_doc_id = _sanitize_filter_value(document_id, "document_id")
        safe_user_id = _sanitize_filter_value(user_id, "user_id")
        filter_expr = f'document_id == "{safe_doc_id}" and user_id == "{safe_user_id}"'
        try:
            await self._async_client.delete(
                collection_name=self.collection_name,
                filter=filter_expr
            )
            try:
                await self._async_client.flush([self.collection_name])
            except Exception:
                pass
            logger.info("Deleted document %s for user %s from Milvus", document_id, user_id)
        except MilvusException as exc:
            logger.error("Failed to delete document %s for user %s from Milvus: %s", document_id, user_id, exc)
            raise RuntimeError(f"Failed to delete document from vector store: {exc}") from exc

    async def close(self) -> None:
        """Release database connections."""
        try:
            self._client.close()
            logger.info("Closed synchronous Milvus client connection")
        except Exception as e:
            logger.warning("Failed to close synchronous Milvus client: %s", e)

        try:
            await self._async_client.close()
            logger.info("Closed asynchronous Milvus client connection")
        except Exception as e:
            logger.warning("Failed to close asynchronous Milvus client: %s", e)
