"""
OPC UA Reader for querying node values and metadata from an OPC UA server.
"""

import logging
from typing import Any, Dict, List
from backend.connectors.opcua.client import OPCUAClient

logger = logging.getLogger(__name__)


class OPCUAReader:
    """Reads values, data types, and timestamps from OPC UA nodes."""

    def __init__(self, client: OPCUAClient):
        self.client = client

    async def read_node_value(self, node_id: str) -> Any:
        """Read current value of a single node by node ID."""
        if not self.client.is_connected:
            raise RuntimeError("OPCUAClient must be connected before reading values.")

        logger.debug(f"Reading value for node {node_id}")
        try:
            if self.client._client is not None:
                node = self.client._client.get_node(node_id)
                value = await node.read_value()
                return value
            else:
                logger.info(f"Reading mock value for node {node_id}")
                return 42.0
        except Exception as e:
            logger.error(f"Error reading node value for {node_id}: {e}", exc_info=True)
            raise

    async def read_multiple_nodes(self, node_ids: List[str]) -> Dict[str, Any]:
        """Read current values for a list of node IDs."""
        results: Dict[str, Any] = {}
        for nid in node_ids:
            try:
                val = await self.read_node_value(nid)
                results[nid] = val
            except Exception as e:
                logger.warning(f"Failed to read node {nid}: {e}")
                results[nid] = None
        return results

    async def read_node_details(self, node_id: str) -> Dict[str, Any]:
        """Read detailed metadata of a node including value, data type, and timestamps."""
        if not self.client.is_connected:
            raise RuntimeError("OPCUAClient must be connected before reading node details.")

        try:
            if self.client._client is not None:
                node = self.client._client.get_node(node_id)
                data_value = await node.read_data_value()
                browse_name = await node.read_browse_name()
                return {
                    "node_id": node_id,
                    "browse_name": browse_name.Name,
                    "value": data_value.Value.Value,
                    "status_code": str(data_value.StatusCode),
                    "source_timestamp": str(data_value.SourceTimestamp),
                    "server_timestamp": str(data_value.ServerTimestamp),
                }
            else:
                return {
                    "node_id": node_id,
                    "browse_name": f"MockNode_{node_id}",
                    "value": 42.0,
                    "status_code": "Good",
                    "source_timestamp": "2026-07-28T00:00:00Z",
                    "server_timestamp": "2026-07-28T00:00:00Z",
                }
        except Exception as e:
            logger.error(f"Error reading node details for {node_id}: {e}", exc_info=True)
            raise
