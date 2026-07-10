import logging
from pathlib import Path
import shutil
from typing import Any

from pymilvus import (
    DataType,
    MilvusClient,
    AsyncMilvusClient,
    MilvusException,
    Function,
    FunctionType,
)

from backend.config.settings import Settings
from backend.vectordb.client import create_milvus_client, create_async_milvus_client

logger = logging.getLogger(__name__)


def effective_index_type(settings: Settings) -> str:
    """Get index type based on deployment environment (Milvus Lite vs Remote)."""
    # Milvus Lite only supports FLAT (README); remote Milvus can use HNSW etc.
    if settings.uses_milvus_lite:
        return "FLAT"
    return settings.milvus_index_type.upper()


def build_index_params(client: MilvusClient, settings: Settings) -> Any:
    """Prepare indexing parameters for embedding and optional sparse fields."""
    index_params = client.prepare_index_params()
    index_type = effective_index_type(settings)

    # Dense vector index on 'embedding' field
    dense_kwargs: dict[str, Any] = {
        "field_name": "embedding",
        "index_type": index_type,
        "metric_type": settings.milvus_metric_type,
    }
    if index_type == "HNSW":
        dense_kwargs["params"] = {
            "M": settings.milvus_m,
            "efConstruction": settings.milvus_ef_construction,
        }
    elif index_type.startswith("IVF"):
        dense_kwargs["params"] = {
            "nlist": settings.milvus_nlist,
        }
    index_params.add_index(**dense_kwargs)

    # Sparse vector index on 'sparse_vector' field (Milvus native BM25)
    if settings.bm25_enabled:
        index_params.add_index(
            field_name="sparse_vector",
            index_type="SPARSE_INVERTED_INDEX",
            metric_type="BM25",
        )

    return index_params


def reconcile_collection_schema(
    client: MilvusClient,
    async_client: AsyncMilvusClient,
    settings: Settings,
) -> tuple[MilvusClient, AsyncMilvusClient]:
    """Verify or create collection and schema, performing reconciliation if mismatch occurs."""
    collection_name = settings.milvus_collection_name
    uri = settings.resolved_milvus_uri

    try:
        if client.has_collection(collection_name):
            try:
                desc = client.describe_collection(collection_name)
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

                metadata_fields = ["document_type", "manufacturer", "equipment", "section"]
                has_metadata = all(f in field_names for f in metadata_fields)

                needs_recreate = (not has_user_id or not is_part_key or not has_metadata)
                # Also recreate if BM25 is enabled but the sparse_vector field is missing
                if settings.bm25_enabled and not has_sparse:
                    needs_recreate = True

                if needs_recreate:
                    if not settings.uses_milvus_lite:
                        logger.error(
                            "Critical: Existing Milvus collection '%s' has schema mismatch "
                            "(missing 'user_id' partition key or 'sparse_vector' field) in production. "
                            "Halt startup to prevent data loss.",
                            collection_name,
                        )
                        raise RuntimeError(
                            f"Database schema mismatch: Collection '{collection_name}' exists "
                            f"but is missing required fields/configuration. "
                            f"Automatic deletion is blocked in production to protect data. "
                            f"Manual migration required."
                        )

                    logger.warning("Existing collection %s needs schema update. Re-creating.", collection_name)
                    try:
                        client.drop_collection(collection_name)
                    except Exception as drop_exc:
                        logger.warning(
                            "Failed to drop collection %s via client (common Milvus Lite Windows bug): %s. "
                            "Attempting to manually delete collection directory.",
                            collection_name, drop_exc
                        )
                        try:
                            client.close()
                            async_client.close()
                        except Exception:
                            pass

                        coll_dir = Path(uri) / "collections" / collection_name
                        if coll_dir.exists():
                            shutil.rmtree(coll_dir, ignore_errors=True)

                        # Re-initialize connections
                        client = create_milvus_client(settings)
                        async_client = create_async_milvus_client(settings)
                else:
                    client.load_collection(collection_name)
                    return client, async_client
            except Exception as exc:
                if isinstance(exc, RuntimeError) and "Database schema mismatch" in str(exc):
                    raise
                logger.exception("Failed to check or load existing collection %s: %s", collection_name, exc)
                raise

        index_type = effective_index_type(settings)
        logger.info(
            "Creating Milvus collection %s (index=%s, bm25=%s, lite=%s)",
            collection_name,
            index_type,
            settings.bm25_enabled,
            settings.uses_milvus_lite,
        )

        schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
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
        schema.add_field("document_type", DataType.VARCHAR, max_length=64)
        schema.add_field("manufacturer", DataType.VARCHAR, max_length=64)
        schema.add_field("equipment", DataType.VARCHAR, max_length=64)
        schema.add_field("section", DataType.VARCHAR, max_length=512)
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=settings.milvus_dimension)

        # Add sparse vector field and BM25 function if enabled
        if settings.bm25_enabled:
            schema.add_field("sparse_vector", DataType.SPARSE_FLOAT_VECTOR)
            bm25_function = Function(
                name="text_bm25",
                input_field_names=["chunk_text"],
                output_field_names=["sparse_vector"],
                function_type=FunctionType.BM25,
            )
            schema.add_function(bm25_function)
            logger.info("Added BM25 function: chunk_text -> sparse_vector")

        client.create_collection(
            collection_name=collection_name,
            schema=schema,
            index_params=build_index_params(client, settings),
        )

        try:
            client.create_index(collection_name=collection_name, field_name="embedding")
        except Exception:
            logger.debug("create_index not required or failed; continuing")

        client.load_collection(collection_name)

    except MilvusException as exc:
        logger.exception("Milvus operation failed: %s", exc)
        raise

    return client, async_client
