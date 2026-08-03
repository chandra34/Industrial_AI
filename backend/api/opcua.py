"""
Admin OPC UA Tag Catalog management API routes.

Provides on-demand catalog re-indexing and status endpoints.
"""

import logging
from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.connectors.opcua.connection import OPCUAClient
from backend.connectors.opcua.config import OPCUAConfig
from backend.connectors.opcua.crawler import OPCUATagCrawler
from backend.connectors.opcua.indexer import get_catalog_status
from backend.database.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/opcua", tags=["OPC UA Admin"])


async def _run_reindex_task() -> None:
    """Background task: connect to OPC UA server, crawl, and index tags."""
    from backend.database.session import AsyncSessionLocal

    opcua_config = OPCUAConfig(_env_file=None)
    opcua_client = OPCUAClient(opcua_config)

    try:
        await opcua_client.connect()
        crawler = OPCUATagCrawler(opcua_client)

        async with AsyncSessionLocal() as db:
            count = await crawler.crawl_and_index(db)
            logger.info("OPC UA reindex background task completed: %d tags indexed.", count)
    except Exception as e:
        logger.error("OPC UA reindex background task failed: %s", e, exc_info=True)
    finally:
        await opcua_client.disconnect()


@router.post("/reindex")
async def reindex_opcua_catalog(background_tasks: BackgroundTasks):
    """Trigger an on-demand OPC UA address space crawl and catalog refresh.

    The crawl runs as a background task so the API responds immediately.
    """
    logger.info("OPC UA catalog reindex triggered by admin.")
    background_tasks.add_task(_run_reindex_task)
    return {
        "status": "sync_started",
        "message": "OPC UA catalog indexing started in background. Check /api/v1/opcua/status for progress.",
    }


@router.get("/status")
async def get_opcua_catalog_status(db: AsyncSession = Depends(get_db)):
    """Return the current OPC UA tag catalog status (tag count and last sync time)."""
    status = await get_catalog_status(db)
    return status
