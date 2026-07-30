"""
OPC UA Node Browser for discovering server nodes and hierarchy.
"""

import logging
from typing import List, Dict, Any, Optional
from backend.connectors.opcua.connection import OPCUAClient
from backend.connectors.opcua.exceptions import OPCUANotConnectedError

logger = logging.getLogger(__name__)


class OPCUABrowser:
    """Discovers nodes and browses node hierarchy on an OPC UA server."""

    def __init__(self, client: OPCUAClient):
        self.client = client

    async def _ensure_connected(self) -> None:
        """Auto-connect client if disconnected."""
        if not self.client.is_connected:
            logger.info("OPC UA client disconnected. Auto-connecting...")
            await self.client.connect()

    async def get_root_node(self) -> Any:
        """Get the root node of the OPC UA server."""
        await self._ensure_connected()
        return self.client.raw_client.get_root_node()

    async def get_objects_node(self) -> Any:
        """Get the Objects folder node."""
        await self._ensure_connected()
        return self.client.raw_client.get_objects_node()

    async def browse_children(self, node_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Browse child nodes of a given node (defaults to Objects node if node_id is None)."""
        await self._ensure_connected()

        nodes_info: List[Dict[str, Any]] = []
        try:
            if node_id:
                parent_node = self.client.raw_client.get_node(node_id)
            else:
                parent_node = self.client.raw_client.get_objects_node()

            children = await parent_node.get_children()
            for child in children:
                browse_name = await child.read_browse_name()
                node_class = await child.read_node_class()
                nodes_info.append({
                    "node_id": str(child.nodeid),
                    "browse_name": browse_name.Name,
                    "node_class": str(node_class),
                })
        except Exception as e:
            logger.error("Error browsing children for node %s: %s", node_id, e, exc_info=True)
            raise

        return nodes_info

    async def search_nodes(self, search_term: str, start_node_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for nodes matching a browse name or node ID pattern in immediate children."""
        all_children = await self.browse_children(start_node_id)
        results = [
            node for node in all_children
            if search_term.lower() in node["browse_name"].lower() or search_term.lower() in node["node_id"].lower()
        ]
        return results
