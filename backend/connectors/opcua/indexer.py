"""
OPC UA Tag Catalog Search Service.

Provides fast keyword-based lookups against the local SQLite tag catalog
for instant agent Node ID resolution without network calls.
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import OPCUATagCatalog

logger = logging.getLogger(__name__)


async def search_local_tag_catalog(
    db: AsyncSession,
    search_term: str,
    top_k: int = 10,
) -> List[Dict[str, Any]]:
    """Search the local OPC UA tag catalog using keyword matching.

    Splits the search_term into individual keywords and matches each
    against display_name, full_path, and browse_name columns.

    :param db: Active async SQLAlchemy session.
    :param search_term: Human language search string (e.g. 'pump line 1 temperature').
    :param top_k: Maximum number of results to return.
    :return: List of matching tag dictionaries with node_id, browse_name, full_path, node_class.
    """
    keywords = search_term.lower().split()
    if not keywords:
        return []

    # Build filter: every keyword must appear in at least one of the searchable columns
    keyword_filters = []
    for kw in keywords:
        pattern = f"%{kw}%"
        keyword_filters.append(
            or_(
                func.lower(OPCUATagCatalog.display_name).like(pattern),
                func.lower(OPCUATagCatalog.full_path).like(pattern),
                func.lower(OPCUATagCatalog.browse_name).like(pattern),
            )
        )

    stmt = (
        select(OPCUATagCatalog)
        .where(*keyword_filters)
        .limit(top_k)
    )

    result = await db.execute(stmt)
    rows = result.scalars().all()

    logger.info("Tag catalog search for '%s' returned %d result(s).", search_term, len(rows))

    return [
        {
            "node_id": tag.node_id,
            "browse_name": tag.browse_name,
            "display_name": tag.display_name,
            "full_path": tag.full_path,
            "node_class": tag.node_class,
            "parent_node_id": tag.parent_node_id,
            "unit": tag.unit,
        }
        for tag in rows
    ]


async def get_catalog_status(db: AsyncSession) -> Dict[str, Any]:
    """Return the current tag catalog status (count + last update time).

    :param db: Active async SQLAlchemy session.
    :return: Dictionary with total_tags and last_updated fields.
    """
    count_result = await db.execute(select(func.count(OPCUATagCatalog.node_id)))
    total = count_result.scalar() or 0

    last_updated = None
    if total > 0:
        ts_result = await db.execute(
            select(func.max(OPCUATagCatalog.updated_at))
        )
        last_updated = ts_result.scalar()

    return {
        "total_tags": total,
        "last_updated": str(last_updated) if last_updated else None,
    }
