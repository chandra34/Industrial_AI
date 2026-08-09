"""
OPC UA Tag Catalog Search Service.

Provides fast keyword-based lookups against the local SQLite tag catalog
for instant agent Node ID resolution without network calls.
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import case, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import OPCUATagCatalog
from backend.connectors.opcua.config import OPCUAConfig

logger = logging.getLogger(__name__)


async def search_local_tag_catalog(
    db: AsyncSession,
    search_term: str,
    top_k: int = 10,
) -> List[Dict[str, Any]]:
    """Search the local OPC UA tag catalog using keyword matching.

    Tier 1: Executes strict AND search across all keywords.
    Tier 2: If Tier 1 returns 0 results, cascades into relaxed OR search
            ranked by keyword match count.

    :param db: Active async SQLAlchemy session.
    :param search_term: Human language search string (e.g. 'pump line 1 temperature').
    :param top_k: Maximum number of results to return.
    :return: List of matching tag dictionaries with node_id, browse_name, full_path, node_class.
    """
    stop_words = {
        "tag", "tags", "in", "the", "of", "a", "an", "for", "val", "value",
        "node", "nodes", "is", "current", "live", "show", "me", "get", "what",
        "give", "find", "check", "tell", "display", "fetch", "read", "sensor",
    }
    raw_keywords = search_term.lower().split()
    keywords = [kw for kw in raw_keywords if kw not in stop_words]
    if not keywords:
        keywords = raw_keywords

    if not keywords:
        return []

    # Tier 1: Build strict AND filter — every keyword must match at least one column
    keyword_filters = []
    for kw in keywords:
        pattern = f"%{kw}%"
        keyword_filters.append(
            or_(
                func.lower(OPCUATagCatalog.display_name).like(pattern),
                func.lower(OPCUATagCatalog.full_path).like(pattern),
                func.lower(OPCUATagCatalog.browse_name).like(pattern),
                func.lower(OPCUATagCatalog.node_id).like(pattern),
            )
        )

    stmt = (
        select(OPCUATagCatalog)
        .where(*keyword_filters)
        .limit(top_k)
    )

    result = await db.execute(stmt)
    rows = result.scalars().all()

    if rows:
        logger.info("Tier 1 strict tag catalog search for '%s' returned %d result(s).", search_term, len(rows))
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

    # Tier 2: Relaxed OR search with per-row keyword match scoring
    logger.info("Tier 1 strict search returned 0 results for '%s'. Cascading to Tier 2 relaxed OR search.", search_term)
    return await _relaxed_or_search(db, keywords, top_k)


async def _relaxed_or_search(
    db: AsyncSession,
    keywords: List[str],
    top_k: int = 10,
) -> List[Dict[str, Any]]:
    """Tier 2: Relaxed OR search with per-row keyword match scoring.

    Matches rows where ANY keyword appears in any searchable column,
    then ranks results by how many distinct keywords matched.
    Requires at least `OPCUAConfig.min_catalog_match_score` matches
    (or 1 if only 1 keyword was provided) to filter out noise.

    :param db: Active async SQLAlchemy session.
    :param keywords: Pre-processed list of lowercase search keywords.
    :param top_k: Maximum number of results to return.
    :return: List of matching tag dictionaries ranked by relevance score.
    """
    if not keywords:
        return []

    # Build per-keyword CASE expressions that each contribute 1 point to match_score
    score_cases = []
    or_conditions = []

    for kw in keywords:
        pattern = f"%{kw}%"
        kw_matches_any_column = or_(
            func.lower(OPCUATagCatalog.display_name).like(pattern),
            func.lower(OPCUATagCatalog.full_path).like(pattern),
            func.lower(OPCUATagCatalog.browse_name).like(pattern),
            func.lower(OPCUATagCatalog.node_id).like(pattern),
        )
        or_conditions.append(kw_matches_any_column)
        score_cases.append(
            case((kw_matches_any_column, literal(1)), else_=literal(0))
        )

    # Sum all per-keyword scores into match_score
    raw_match_score = sum(score_cases)
    match_score = raw_match_score.label("match_score")

    # Read configurable minimum match threshold (default 2, cap at len(keywords))
    config = OPCUAConfig(_env_file=None)
    min_threshold = min(config.min_catalog_match_score, len(keywords))

    stmt = (
        select(OPCUATagCatalog, match_score)
        .where(or_(*or_conditions), raw_match_score >= min_threshold)
        .order_by(match_score.desc())
        .limit(top_k)
    )

    result = await db.execute(stmt)
    rows = result.all()

    logger.info(
        "Tier 2 relaxed OR search returned %d result(s) for keywords %s (min threshold: %d).",
        len(rows),
        keywords,
        min_threshold,
    )

    return [
        {
            "node_id": tag.node_id,
            "browse_name": tag.browse_name,
            "display_name": tag.display_name,
            "full_path": tag.full_path,
            "node_class": tag.node_class,
            "parent_node_id": tag.parent_node_id,
            "unit": tag.unit,
            "match_score": score,
        }
        for tag, score in rows
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
