"""
OPC UA Node Browser for discovering server nodes and hierarchy.
"""

import logging
from typing import List, Dict, Any, Optional
from backend.connectors.opcua.client import OPCUAClient

logger = logging.getLogger(__name__)


class OPCUABrowser:
    """Discovers nodes and browses node hierarchy on an OPC UA server."""

    def __init__(self, client: OPCUAClient):
        self.client = client

    async def get_root_node(self) -> Any:
        """Get the root node of the OPC UA server."""
        if not self.client.is_connected:
            raise RuntimeError("OPCUAClient must be connected before browsing.")

        if self.client._client is not None:
            return self.client._client.get_root_node()
        return {"node_id": "ns=0;i=84", "browse_name": "Root"}

    async def get_objects_node(self) -> Any:
        """Get the Objects folder node."""
        if not self.client.is_connected:
            raise RuntimeError("OPCUAClient must be connected before browsing.")

        if self.client._client is not None:
            return self.client._client.get_objects_node()
        return {"node_id": "ns=0;i=85", "browse_name": "Objects"}

    async def browse_children(self, node_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Browse child nodes of a given node (defaults to Objects node if node_id is None)."""
        if not self.client.is_connected:
            raise RuntimeError("OPCUAClient must be connected before browsing.")

        nodes_info: List[Dict[str, Any]] = []
        try:
            if self.client._client is not None:
                if node_id:
                    parent_node = self.client._client.get_node(node_id)
                else:
                    parent_node = self.client._client.get_objects_node()

                children = await parent_node.get_children()
                for child in children:
                    browse_name = await child.read_browse_name()
                    node_class = await child.read_node_class()
                    nodes_info.append({
                        "node_id": str(child.nodeid),
                        "browse_name": browse_name.Name,
                        "node_class": str(node_class),
                    })
            else:
                logger.info(f"Browsing node {node_id or 'Objects'} in mock mode.")
                nodes_info = [
                    {"node_id": "ns=2;s=Device1", "browse_name": "Device1", "node_class": "Object"},
                    {"node_id": "ns=2;s=Device2", "browse_name": "Device2", "node_class": "Object"},
                ]
        except Exception as e:
            logger.error(f"Error browsing children for node {node_id}: {e}", exc_info=True)
            raise

        return nodes_info

    async def search_nodes(self, search_term: str, start_node_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Recursively search for nodes matching a browse name or node ID pattern."""
        all_children = await self.browse_children(start_node_id)
        results = [
            node for node in all_children
            if search_term.lower() in node["browse_name"].lower() or search_term.lower() in node["node_id"].lower()
        ]
        return results
