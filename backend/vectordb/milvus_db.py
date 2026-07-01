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

from pymilvus import DataType, MilvusClient, MilvusException, AsyncMilvusClient  # noqa: E402


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
        kwargs: dict[str, Any] = {
            "field_name": "embedding",
            "index_type": index_type,
            "metric_type": self.settings.milvus_metric_type,
        }
        if index_type == "HNSW":
            kwargs["params"] = {
                "M": self.settings.milvus_m,
                "efConstruction": self.settings.milvus_ef_construction,
            }
        elif index_type.startswith("IVF"):
            kwargs["params"] = {
                "nlist": self.settings.milvus_nlist,
            }
        index_params.add_index(**kwargs)
        return index_params

    def _search_params(self) -> dict[str, Any]:
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
                    is_part_key = False
                    if user_id_field:
                        is_part_key = user_id_field.get("is_partition_key", False) if isinstance(user_id_field, dict) else getattr(user_id_field, "is_partition_key", False)

                    if not has_user_id or not is_part_key:
                        if not self.settings.uses_milvus_lite:
                            logger.error(
                                "Critical: Existing Milvus collection '%s' has schema mismatch "
                                "(missing 'user_id' field or partition key config) in production. "
                                "Halt startup to prevent data loss.",
                                self.collection_name,
                            )
                            raise RuntimeError(
                                f"Database schema mismatch: Collection '{self.collection_name}' exists "
                                f"but is missing the required 'user_id' partition key configuration. "
                                f"Automatic deletion is blocked in production to protect data. "
                                f"Manual migration required."
                            )

                        logger.warning("Existing collection %s lacks 'user_id' field or partition key config. Re-creating.", self.collection_name)
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
                "Creating Milvus collection %s (index=%s, lite=%s)",
                self.collection_name,
                index_type,
                self.settings.uses_milvus_lite,
            )

            schema = self._client.create_schema(auto_id=True, enable_dynamic_field=False)
            schema.add_field("id", DataType.INT64, is_primary=True)
            schema.add_field("document_id", DataType.VARCHAR, max_length=64)
            schema.add_field("user_id", DataType.VARCHAR, max_length=64, is_partition_key=True)
            schema.add_field("source_filename", DataType.VARCHAR, max_length=512)
            schema.add_field("page_number", DataType.INT64)
            schema.add_field("chunk_index", DataType.INT64)
            schema.add_field("chunk_text", DataType.VARCHAR, max_length=65535)
            schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=self.settings.milvus_dimension)

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
        """Insert chunk embeddings into Milvus for ``user_id`` and return the count inserted."""
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
        """Perform a vector similarity search scoped to ``user_id``."""
        if query_embedding.ndim == 1:
            query_embedding = np.expand_dims(query_embedding, axis=0)

        results = await self._async_client.search(
            collection_name=self.collection_name,
            data=query_embedding.tolist(),
            limit=top_k,
            filter=f'user_id == "{_sanitize_filter_value(user_id, "user_id")}"',
            search_params=self._search_params(),
            output_fields=["document_id", "source_filename", "page_number", "chunk_index", "chunk_text"],
        )

        hits: list[VectorSearchHit] = []
        for batch in results:
            for hit in batch:
                entity = getattr(hit, "entity", None) or (hit.get("entity") if isinstance(hit, dict) else {})
                score = (
                    getattr(hit, "distance", None)
                    or getattr(hit, "score", None)
                    or (hit.get("distance") if isinstance(hit, dict) else None)
                    or (hit.get("score") if isinstance(hit, dict) else None)
                )

                hits.append(
                    VectorSearchHit(
                        document_id=str(entity.get("document_id")),
                        source_filename=str(entity.get("source_filename")),
                        page_number=int(entity.get("page_number") or 0),
                        chunk_index=int(entity.get("chunk_index") or 0),
                        chunk_text=str(entity.get("chunk_text") or ""),
                        score=float(score) if score is not None else 0.0,
                    )
                )

        return hits

    async def list_documents(self, user_id: str) -> list[dict]:
        """List all unique documents and compute page/chunk metadata for a specific user."""
        if not await self._async_client.has_collection(self.collection_name):
            return []

        docs_map: dict[str, dict] = {}
        page_limit = 5000
        offset = 0
        safe_user_id = _sanitize_filter_value(user_id, "user_id")

        while True:
            try:
                results = await self._async_client.query(
                    collection_name=self.collection_name,
                    filter=f"id >= 0 and user_id == '{safe_user_id}'",
                    output_fields=["document_id", "source_filename", "page_number"],
                    limit=page_limit,
                    offset=offset,
                )
            except MilvusException as exc:
                logger.error("Failed to query documents from Milvus: %s", exc)
                return list(docs_map.values())

            if not results:
                break

            for row in results:
                doc_id = row.get("document_id")
                filename = row.get("source_filename")
                page_num = row.get("page_number", 1)
                if not doc_id:
                    continue

                if filename and filename.startswith(f"{doc_id}_"):
                    pretty_name = filename[len(doc_id) + 1 :]
                else:
                    pretty_name = filename or "Unknown"

                if doc_id not in docs_map:
                    docs_map[doc_id] = {
                        "document_id": doc_id,
                        "filename": pretty_name,
                        "page_count": 0,
                        "chunk_count": 0,
                    }
                docs_map[doc_id]["chunk_count"] += 1
                if page_num > docs_map[doc_id]["page_count"]:
                    docs_map[doc_id]["page_count"] = page_num

            if len(results) < page_limit:
                break

            offset += page_limit

        return list(docs_map.values())

    async def delete_document(self, document_id: str, user_id: str) -> None:
        """Delete all vectors for the specified document_id and user_id."""
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

    async def get_all_chunk_texts(self, user_id: str) -> list[str]:
        """Return all chunk_text values stored for *user_id*.

        Used to rebuild the BM25 sparse index after a document deletion.
        """
        if not await self._async_client.has_collection(self.collection_name):
            return []

        chunk_texts: list[str] = []
        page_limit = 5000
        offset = 0
        safe_user_id = _sanitize_filter_value(user_id, "user_id")

        while True:
            try:
                results = await self._async_client.query(
                    collection_name=self.collection_name,
                    filter=f'user_id == "{safe_user_id}"',
                    output_fields=["chunk_text"],
                    limit=page_limit,
                    offset=offset,
                )
            except MilvusException as exc:
                logger.error("Failed to query chunk texts for user %s: %s", user_id, exc)
                break

            if not results:
                break

            for row in results:
                text = row.get("chunk_text")
                if text:
                    chunk_texts.append(str(text))

            if len(results) < page_limit:
                break

            offset += page_limit

        return chunk_texts

    async def get_chunks_by_text(self, texts: list[str], user_id: str) -> list[VectorSearchHit]:
        """Query Milvus to retrieve metadata for a list of chunk texts."""
        if not await self._async_client.has_collection(self.collection_name) or not texts:
            return []
        
        safe_user_id = _sanitize_filter_value(user_id, "user_id")
        
        # Escape backslashes, double quotes, newlines, and carriage returns in chunk texts to prevent injection/syntax errors
        escaped_texts = []
        for t in texts:
            escaped = t.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")
            escaped_texts.append(f'"{escaped}"')
            
        texts_expr = ", ".join(escaped_texts)
        filter_expr = f'user_id == "{safe_user_id}" and chunk_text in [{texts_expr}]'
        
        try:
            results = await self._async_client.query(
                collection_name=self.collection_name,
                filter=filter_expr,
                output_fields=["document_id", "source_filename", "page_number", "chunk_index", "chunk_text"],
                limit=len(texts) * 2,
            )
        except MilvusException as exc:
            logger.error("Failed to query chunks by text: %s", exc)
            return []
            
        hits = []
        for row in results:
            hits.append(
                VectorSearchHit(
                    document_id=str(row.get("document_id", "")),
                    source_filename=str(row.get("source_filename", "")),
                    page_number=int(row.get("page_number", 0)),
                    chunk_index=int(row.get("chunk_index", 0)),
                    chunk_text=str(row.get("chunk_text", "")),
                    score=0.0,
                )
            )
        return hits

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
