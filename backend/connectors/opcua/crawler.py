"""
OPC UA Address Space Crawler for building the local Tag Catalog.

Recursively scans the OPC UA server node hierarchy and persists
discovered machines (Objects) and sensors (Variables) into SQLite
for instant agent lookups.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.connectors.opcua.connection import OPCUAClient
from backend.connectors.opcua.utils import clean_node_id
from backend.database.models import OPCUATagCatalog

logger = logging.getLogger(__name__)

# Standard OPC UA Alarm Condition metadata sub-properties (IEC 62541-9)
ALARM_METADATA_FIELDS = {
    "AckedState", "ActiveState", "BranchId", "Comment", "ConditionClassId",
    "ConditionClassName", "ConfirmedState", "DialogState", "EnabledState",
    "EventId", "EventType", "HighHighLimit", "HighLimit", "InputNode",
    "LastSeverity", "LimitState", "LowLowLimit", "LowLimit", "Message",
    "Quality", "ReceiveTime", "Retain", "Severity", "SourceNode",
    "SourceName", "SuppressedOrShelved", "Time", "ClientUserId", "CurrentState",
}


class OPCUATagCrawler:
    """Recursively crawls OPC UA address space and caches tags into SQLite."""

    def __init__(self, client: OPCUAClient, max_depth: int = 5) -> None:
        """Initialize the Tag Crawler.

        :param client: Connected or connectable OPCUAClient instance.
        :param max_depth: Maximum folder recursion depth (default 5).
        """
        self.client = client
        self.max_depth = max_depth
        self._visited: Set[str] = set()

    async def crawl_and_index(self, db: AsyncSession) -> int:
        """Crawl the OPC UA address space and persist tags to database.

        :param db: Active async SQLAlchemy session.
        :return: Number of tags indexed.
        """
        if not self.client.is_connected:
            await self.client.connect()

        logger.info("Starting OPC UA address space crawl (max_depth=%d)...", self.max_depth)
        self._visited.clear()
        tags: List[Dict[str, Any]] = []

        root_objects = self.client.raw_client.get_objects_node()
        await self._crawl_node(
            node=root_objects,
            path="Objects",
            parent_node_id=None,
            depth=1,
            accumulator=tags,
        )

        # Clear old catalog and insert fresh tags (deduplicated by node_id)
        await db.execute(delete(OPCUATagCatalog))
        now = datetime.now(timezone.utc)
        unique_tags: Dict[str, Dict[str, Any]] = {}
        for tag in tags:
            unique_tags[tag["node_id"]] = tag

        for tag in unique_tags.values():
            tag["updated_at"] = now
            db.add(OPCUATagCatalog(**tag))
        await db.commit()

        logger.info("Successfully indexed %d OPC UA tags into local catalog.", len(unique_tags))
        return len(unique_tags)


    async def _crawl_node(
        self,
        node: Any,
        path: str,
        parent_node_id: Optional[str],
        depth: int,
        accumulator: List[Dict[str, Any]],
    ) -> None:
        """Recursively crawl a single node and its children.

        Uses get_children_descriptions for single-roundtrip batch extraction of
        BrowseName, NodeClass, and NodeId.

        :param node: asyncua Node object.
        :param path: Human-readable path built so far.
        :param parent_node_id: Node ID string of the parent.
        :param depth: Current recursion depth.
        :param accumulator: List to append discovered tag dictionaries.
        """
        node_id_str = clean_node_id(node.nodeid)

        if node_id_str in self._visited or depth > self.max_depth:
            return
        self._visited.add(node_id_str)

        try:
            # Batch extraction: get_children_descriptions returns BrowseName, NodeClass, and NodeId in 1 call
            descriptions = await node.get_children_descriptions()
        except Exception as e:
            logger.warning("Failed to get children descriptions for node %s: %s", node_id_str, e)
            return

        for desc in descriptions:
            try:
                child_node_id = clean_node_id(desc.NodeId)
                browse_name = getattr(desc.BrowseName, "Name", str(desc.BrowseName))

                # Skip internal OPC UA protocol diagnostic / system folders
                if depth == 1 and browse_name in ["Server", "Aliases", "Locations", "MemoryBuffers"]:
                    logger.debug("Skipping standard OPC UA system folder: %s", browse_name)
                    continue

                # Skip internal Alarm Condition metadata sub-variables (e.g. MyLevel.Alarm/0:Comment)
                if "/0:" in child_node_id or browse_name in ALARM_METADATA_FIELDS:
                    continue

                node_class_val = getattr(desc.NodeClass, "name", str(desc.NodeClass))
                child_path = f"{path} > {browse_name}"

                # Build human-readable display name from path segments (normalize # and _ -> space)
                display_name = " ".join(
                    seg.replace("_", " ").replace("#", " ")
                    for seg in child_path.split(" > ")
                    if seg != "Objects"
                )

                tag_record: Dict[str, Any] = {
                    "node_id": child_node_id,
                    "browse_name": browse_name,
                    "display_name": display_name.strip(),
                    "full_path": child_path,
                    "node_class": "Variable" if "Variable" in node_class_val else "Object",
                    "parent_node_id": node_id_str,
                }

                if "Variable" in node_class_val:
                    accumulator.append(tag_record)
                elif "Object" in node_class_val or "Folder" in node_class_val:
                    accumulator.append(tag_record)
                    child_node = self.client.raw_client.get_node(desc.NodeId)
                    await self._crawl_node(
                        node=child_node,
                        path=child_path,
                        parent_node_id=child_node_id,
                        depth=depth + 1,
                        accumulator=accumulator,
                    )
            except Exception as e:
                logger.warning("Error processing child node under %s: %s", node_id_str, e)
                continue
