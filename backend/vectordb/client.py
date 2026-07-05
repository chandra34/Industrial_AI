import logging
import os
from typing import Optional

from backend.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

# pymilvus validates os.environ["MILVUS_URI"] at import time (http(s) only).
# Never set MILVUS_URI to a .db path before "from pymilvus import ...".
# The real .db path is passed to MilvusClient(...) only when the store is created.
_IMPORT_PLACEHOLDER_URI = "http://127.0.0.1:19530"


def bootstrap_pymilvus_environment(settings: Settings) -> str:
    """
    Load Milvus Lite and satisfy pymilvus import-time URI checks.

    For .db URIs: import milvus_lite, set a temporary http MILVUS_URI for import only,
    then pass the resolved .db path to MilvusClient(db_path) in create_milvus_client().
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


bootstrap_pymilvus_environment(get_settings())

from pymilvus import (  # noqa: E402
    MilvusClient,
    AsyncMilvusClient,
    MilvusException,
)


def create_milvus_client(settings: Settings) -> MilvusClient:
    """Create a synchronous MilvusClient."""
    uri = settings.resolved_milvus_uri
    token: Optional[str] = getattr(settings, "milvus_token", None)
    logger.info(
        "Connecting to Milvus at %s (lite=%s)",
        uri,
        settings.uses_milvus_lite,
    )
    try:
        # Milvus Lite: local file path (official API: MilvusClient("./file.db"))
        if settings.uses_milvus_lite:
            return MilvusClient(uri)

        # Remote Milvus server
        if token:
            return MilvusClient(uri=uri, token=token)
        return MilvusClient(uri=uri)
    except MilvusException as exc:
        hint = ""
        if "19530" in str(exc):
            hint = (
                " No Milvus server is running on localhost:19530. "
                "For embedded storage, set MILVUS_URI to an absolute path ending in .db "
                "(e.g. MILVUS_URI=./milvus_local.db) and install milvus-lite."
            )
        raise RuntimeError(f"Failed to connect to Milvus at {uri}.{hint}") from exc


def create_async_milvus_client(settings: Settings) -> AsyncMilvusClient:
    """Create an AsyncMilvusClient."""
    uri = settings.resolved_milvus_uri
    token: Optional[str] = getattr(settings, "milvus_token", None)
    try:
        if settings.uses_milvus_lite:
            return AsyncMilvusClient(uri)
        if token:
            return AsyncMilvusClient(uri=uri, token=token)
        return AsyncMilvusClient(uri=uri)
    except MilvusException as exc:
        raise RuntimeError(f"Failed to connect to AsyncMilvusClient at {uri}") from exc


async def close_clients(client: MilvusClient, async_client: AsyncMilvusClient) -> None:
    """Release database connections."""
    try:
        client.close()
        logger.info("Closed synchronous Milvus client connection")
    except Exception as e:
        logger.warning("Failed to close synchronous Milvus client: %s", e)

    try:
        await async_client.close()
        logger.info("Closed asynchronous Milvus client connection")
    except Exception as e:
        logger.warning("Failed to close asynchronous Milvus client: %s", e)


def run_health_check(client: MilvusClient) -> bool:
    """Verify connection to Milvus by checking if list_collections works."""
    try:
        client.list_collections()
        return True
    except Exception as exc:
        logger.error("Milvus health check failed: %s", exc)
        return False
