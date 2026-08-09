"""
OPC UA Node Browser for discovering server nodes and hierarchy.
"""

import logging
from typing import List, Dict, Any, Optional
from backend.connectors.opcua.connection import OPCUAClient
from backend.connectors.opcua.exceptions import OPCUANotConnectedError

logger = logging.getLogger(__name__)


from backend.connectors.opcua.utils import clean_node_id


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
                node_id = clean_node_id(node_id)
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

    async def translate_browse_path(
        self,
        path_string: str,
        starting_node_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Translate a human-readable browse path to a Node ID.

        Supports formats like:
          - "Objects > Simulation > Counter"
          - "/3:Simulation/3:Counter"

        :param path_string: The browse path string.
        :param starting_node_id: Node ID to start translation from (default: Objects folder).
        :return: Dict containing browse_path, status, and node_id if found.
        """
        await self._ensure_connected()
        from asyncua import ua

        try:
            # Determine starting node
            if starting_node_id:
                clean_start_id = clean_node_id(starting_node_id)
                start_node = self.client.raw_client.get_node(clean_start_id)
            else:
                start_node = self.client.raw_client.get_objects_node()

            start_node_id_str = str(start_node.nodeid)
            # Parse default namespace index from starting node to use as fallback
            default_ns = 0
            if "ns=" in start_node_id_str:
                try:
                    default_ns = int(start_node_id_str.split(";")[0].replace("ns=", ""))
                except Exception:
                    pass

            # Process relative path string
            relative_path_string = ""
            if path_string.startswith("/"):
                relative_path_string = path_string
            else:
                # Format: "Objects > Simulation > Counter" or "Simulation > Counter"
                segments = [s.strip() for s in path_string.split(">") if s.strip()]
                # Skip leading "Objects" if we are starting from the Objects node
                if segments and segments[0].lower() == "objects" and not starting_node_id:
                    segments = segments[1:]

                path_parts = []
                for seg in segments:
                    if ":" in seg:
                        # Already has namespace prefix (e.g. "3:Simulation")
                        path_parts.append(seg)
                    else:
                        # Use default ns fallback (e.g. "3:Simulation")
                        # For root server/objects nodes, keep namespace 0
                        if seg.lower() in ["server", "objects"]:
                            path_parts.append(f"0:{seg}")
                        else:
                            path_parts.append(f"{default_ns}:{seg}")
                relative_path_string = "/" + "/".join(path_parts)

            logger.info("Translating browse path relative string: %s", relative_path_string)
            results = await self.client.raw_client.translate_browsepaths(
                start_node, [relative_path_string]
            )

            if results and results[0].Targets:
                target_node_id = str(results[0].Targets[0].TargetId)
                clean_target_id = clean_node_id(target_node_id)
                return {
                    "browse_path": path_string,
                    "status": "Success",
                    "node_id": clean_target_id,
                }
            else:
                return {
                    "browse_path": path_string,
                    "status": "NotFound",
                    "node_id": None,
                    "note": "Path could not be resolved on the OPC UA server.",
                }

        except Exception as e:
            logger.error("Error translating browse path '%s': %s", path_string, e, exc_info=True)
            return {
                "browse_path": path_string,
                "status": "Failed",
                "node_id": None,
                "error": str(e),
            }
