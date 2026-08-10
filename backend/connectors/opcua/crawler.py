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
from backend.database.models import OPCUATagCatalog

logger = logging.getLogger(__name__)


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

        :param node: asyncua Node object.
        :param path: Human-readable path built so far.
        :param parent_node_id: Node ID string of the parent.
        :param depth: Current recursion depth.
        :param accumulator: List to append discovered tag dictionaries.
        """
        node_id_str = str(node.nodeid)

        if node_id_str in self._visited or depth > self.max_depth:
            return
        self._visited.add(node_id_str)

        try:
            children = await node.get_children()
        except Exception as e:
            logger.warning("Failed to get children for node %s: %s", node_id_str, e)
            return

        for child in children:
            try:
                child_node_id = str(child.nodeid)
                browse_name_obj = await child.read_browse_name()
                browse_name = browse_name_obj.Name

                # Crawl internal OPC UA system folder (Objects > Server) to reach custom folders like Server > Boilers
                if depth == 1 and browse_name == "Server":
                    pass

                # Skip dummy OPC UA memory buffer test folder
                if browse_name == "MemoryBuffers":
                    continue

                node_class_obj = await child.read_node_class()
                node_class = getattr(node_class_obj, "name", str(node_class_obj))
                child_path = f"{path} > {browse_name}"

                # Build human-readable display name from path segments (normalize # -> space)
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
                    "node_class": "Variable" if "Variable" in node_class else "Object",
                    "parent_node_id": node_id_str,
                }


                if "Variable" in node_class:
                    accumulator.append(tag_record)
                elif "Object" in node_class or "Folder" in node_class:
                    accumulator.append(tag_record)
                    await self._crawl_node(
                        node=child,
                        path=child_path,
                        parent_node_id=child_node_id,
                        depth=depth + 1,
                        accumulator=accumulator,
                    )
            except Exception as e:
                logger.warning("Error processing child node under %s: %s", node_id_str, e)
                continue
