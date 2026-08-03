"""
OPC UA Reader for querying node values and metadata from an OPC UA server.
"""

import logging
from typing import Any, Dict, List
from backend.connectors.opcua.connection import OPCUAClient
from backend.connectors.opcua.exceptions import OPCUANotConnectedError

logger = logging.getLogger(__name__)


def _clean_node_id(node_id: str) -> str:
    """Clean ExpandedNodeId representation to a parseable string format."""
    import re
    if "ExpandedNodeId" in node_id:
        ns_match = re.search(r"NamespaceIndex=(\d+)", node_id)
        id_match = re.search(r"Identifier=([^,\)]+)", node_id)
        if ns_match and id_match:
            ns = ns_match.group(1)
            ident = id_match.group(1).strip("'\"")
            if ident.isdigit():
                return f"ns={ns};i={ident}"
            else:
                return f"ns={ns};s={ident}"
    return node_id


class OPCUAReader:
    """Reads values, data types, and timestamps from OPC UA nodes."""

    def __init__(self, client: OPCUAClient):
        self.client = client

    async def _ensure_connected(self) -> None:
        """Auto-connect client if disconnected."""
        if not self.client.is_connected:
            logger.info("OPC UA client disconnected. Auto-connecting...")
            await self.client.connect()

    async def read_node_value(self, node_id: str) -> Any:
        """Read current value of a single node by node ID."""
        await self._ensure_connected()

        node_id = _clean_node_id(node_id)
        logger.debug("Reading value for node %s", node_id)
        try:
            node = self.client.raw_client.get_node(node_id)
            value = await node.read_value()
            if value is not None and not isinstance(value, (int, float, str, bool, list, dict)):
                value = str(value)
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
        await self._ensure_connected()

        node_id = _clean_node_id(node_id)
        try:
            node = self.client.raw_client.get_node(node_id)
            data_value = await node.read_data_value()
            browse_name = await node.read_browse_name()
            val = data_value.Value.Value if data_value and data_value.Value is not None else None
            if val is not None and not isinstance(val, (int, float, str, bool, list, dict)):
                val = str(val)
            return {
                "node_id": node_id,
                "browse_name": str(browse_name.Name) if hasattr(browse_name, "Name") else str(browse_name),
                "value": val,
                "status_code": str(data_value.StatusCode) if data_value else "Unknown",
                "source_timestamp": str(data_value.SourceTimestamp) if data_value else "N/A",
                "server_timestamp": str(data_value.ServerTimestamp) if data_value else "N/A",
            }
        except Exception as e:
            logger.error(f"Error reading node details for {node_id}: {e}", exc_info=True)
            raise

    async def read_machine_telemetry(self, machine_node_id: str) -> Dict[str, Any]:
        """Read ALL live sensor values for a machine by its parent Object node ID.

        Recursively discovers all child Variable nodes (handles flat and nested
        sub-folder structures) and batch-reads their current values.

        :param machine_node_id: OPC UA Node ID of the machine Object (e.g. 'ns=2;s=Line1.Pump01').
        :return: Dictionary with machine_node_id, sensor_count, and telemetry readings.
        """
        await self._ensure_connected()

        machine_node_id = _clean_node_id(machine_node_id)
        logger.info("Reading full machine telemetry for node: %s", machine_node_id)
        machine_node = self.client.raw_client.get_node(machine_node_id)


        # Recursively find all child Variable nodes
        sensor_nodes = await self._collect_variable_children(machine_node)

        if not sensor_nodes:
            return {
                "machine_node_id": machine_node_id,
                "sensor_count": 0,
                "telemetry": {},
                "note": "No sensor variables found under this node.",
            }

        # Batch read all sensor values
        telemetry: Dict[str, Any] = {}
        for sensor_node in sensor_nodes:
            sensor_id = str(sensor_node.nodeid)
            try:
                browse_name = await sensor_node.read_browse_name()
                name = browse_name.Name if hasattr(browse_name, "Name") else str(browse_name)
                value = await sensor_node.read_value()
                if value is not None and not isinstance(value, (int, float, str, bool, list, dict)):
                    value = str(value)
                telemetry[name] = {
                    "node_id": sensor_id,
                    "value": value,
                }
            except Exception as e:
                logger.warning("Failed to read sensor %s: %s", sensor_id, e)
                telemetry[sensor_id] = {"node_id": sensor_id, "error": str(e)}

        return {
            "machine_node_id": machine_node_id,
            "sensor_count": len(telemetry),
            "telemetry": telemetry,
        }

    async def _collect_variable_children(self, node: Any) -> list:
        """Recursively collect all Variable (sensor) nodes under a given node.

        Handles both flat structures (sensors directly under machine) and
        nested sub-folder structures (sensors inside grouped folders).

        :param node: asyncua Node object to search under.
        :return: List of asyncua Node objects with NodeClass == Variable.
        """
        sensor_nodes = []
        try:
            children = await node.get_children()
            for child in children:
                node_class_obj = await child.read_node_class()
                node_class = getattr(node_class_obj, "name", str(node_class_obj))
                if "Variable" in node_class:
                    sensor_nodes.append(child)
                elif "Object" in node_class or "Folder" in node_class:
                    # Recurse into sub-folders
                    sub_sensors = await self._collect_variable_children(child)
                    sensor_nodes.extend(sub_sensors)

        except Exception as e:
            logger.warning("Error collecting children for node %s: %s", str(node.nodeid), e)
        return sensor_nodes

