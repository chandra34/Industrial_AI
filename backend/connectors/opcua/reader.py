"""
OPC UA Reader for querying node values and metadata from an OPC UA server.
"""

import logging
from typing import Any, Dict, List
from backend.connectors.opcua.connection import OPCUAClient
from backend.connectors.opcua.exceptions import OPCUANotConnectedError

logger = logging.getLogger(__name__)


class OPCUAReader:
    """Reads values, data types, and timestamps from OPC UA nodes."""

    def __init__(self, client: OPCUAClient):
        self.client = client

    async def read_node_value(self, node_id: str) -> Any:
        """Read current value of a single node by node ID."""
        if self.client._client is None:
            raise OPCUANotConnectedError(
                "OPCUAClient must be connected before reading values. Call connect() first."
            )

        logger.debug("Reading value for node %s", node_id)
        try:
            node = self.client._client.get_node(node_id)
            value = await node.read_value()
            return value
        except Exception as e:
            logger.error("Error reading node value for %s: %s", node_id, e, exc_info=True)
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
        if self.client._client is None:
            raise OPCUANotConnectedError(
                "OPCUAClient must be connected before reading node details. Call connect() first."
            )

        try:
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
        except Exception as e:
            logger.error(f"Error reading node details for {node_id}: {e}", exc_info=True)
            raise
