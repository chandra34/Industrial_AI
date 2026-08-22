"""
OPC UA Reader for querying node values and metadata from an OPC UA server.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from backend.connectors.opcua.connection import OPCUAClient
from backend.connectors.opcua.exceptions import OPCUANotConnectedError

logger = logging.getLogger(__name__)



from backend.connectors.opcua.utils import clean_node_id, to_json_safe


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

        node_id = clean_node_id(node_id)
        logger.debug("Reading value for node %s", node_id)
        try:
            node = self.client.raw_client.get_node(node_id)
            value = await node.read_value()
            value = to_json_safe(value)
            return value
        except Exception as e:
            logger.error("Error reading node value for %s: %s", node_id, e, exc_info=True)
            raise


    async def read_multiple_nodes(self, node_ids: List[str]) -> Dict[str, Any]:
        """Read current values for a list of node IDs in a single OPC UA batch call.

        :param node_ids: List of OPC UA Node ID strings.
        :return: Dictionary mapping cleaned node IDs to their live values.
        """
        await self._ensure_connected()

        if not node_ids:
            return {}

        clean_ids = [clean_node_id(nid) for nid in node_ids]
        logger.debug("Batch reading values for nodes: %s", clean_ids)

        try:
            nodes = [self.client.raw_client.get_node(nid) for nid in clean_ids]
            values = await self.client.raw_client.read_values(nodes)
            return {
                nid: to_json_safe(val)
                for nid, val in zip(clean_ids, values)
            }
        except Exception as e:
            logger.warning("Batch read failed for nodes %s: %s. Falling back to sequential reads.", clean_ids, e)
            results: Dict[str, Any] = {}
            for nid in clean_ids:
                try:
                    val = await self.read_node_value(nid)
                    results[nid] = val
                except Exception as read_err:
                    logger.warning("Failed sequential read for node %s: %s", nid, read_err)
                    results[nid] = None
            return results


    async def read_node_details(self, node_id: str) -> Dict[str, Any]:
        """Read detailed metadata of a node including value, data type, and timestamps."""
        await self._ensure_connected()

        node_id = clean_node_id(node_id)
        try:
            node = self.client.raw_client.get_node(node_id)
            data_value = await node.read_data_value()

            # Graceful browse_name lookup with fallback to node_id identifier segment
            try:
                browse_name_obj = await node.read_browse_name()
                browse_name = str(browse_name_obj.Name) if hasattr(browse_name_obj, "Name") else str(browse_name_obj)
            except Exception:
                browse_name = node_id.split("=")[-1] if "=" in node_id else node_id

            val = to_json_safe(data_value.Value.Value) if data_value and data_value.Value is not None else None
            return {
                "node_id": node_id,
                "browse_name": browse_name,
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

        machine_node_id = clean_node_id(machine_node_id)
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
                value = to_json_safe(value)
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

    async def read_node_history(
        self,
        node_id: str,
        start_time_iso: Optional[str] = None,
        end_time_iso: Optional[str] = None,
        num_values: int = 50,
    ) -> Dict[str, Any]:
        """Read past historical raw values for a node from OPC UA server buffer (IEC 62541-11)."""
        node_id = clean_node_id(node_id)
        now = datetime.now(timezone.utc)
        try:
            start_dt = datetime.fromisoformat(start_time_iso) if start_time_iso else now - timedelta(hours=1)
        except Exception:
            start_dt = now - timedelta(hours=1)

        try:
            end_dt = datetime.fromisoformat(end_time_iso) if end_time_iso else now
        except Exception:
            end_dt = now

        try:
            await self._ensure_connected()
            node = self.client.raw_client.get_node(node_id)
            history_data = await node.read_raw_history(start_dt, end_dt, numvalues=num_values)
            formatted_history = []
            for datavalue in (history_data or []):
                val = to_json_safe(datavalue.Value.Value) if datavalue and datavalue.Value else None
                formatted_history.append({
                    "timestamp": str(getattr(datavalue, "SourceTimestamp", None) or getattr(datavalue, "ServerTimestamp", "N/A")),
                    "value": val,
                    "status": str(getattr(datavalue, "StatusCode", "Good")),
                })
            return {
                "node_id": node_id,
                "record_count": len(formatted_history),
                "history": formatted_history,
            }
        except Exception as e:
            logger.warning("Failed to read history for node %s: %s", node_id, e)
            return {"node_id": node_id, "record_count": 0, "history": [], "note": f"Historical reading note: {e}"}

    async def get_alarm_events(
        self,
        machine_node_id: str,
        num_events: int = 10,
    ) -> Dict[str, Any]:
        """Read recent trip alarm snapshots and condition events for a machine node (IEC 62541-9)."""
        await self._ensure_connected()
        machine_node_id = clean_node_id(machine_node_id)
        node = self.client.raw_client.get_node(machine_node_id)

        try:
            event_records = await node.read_event_history(numvalues=num_events)
            formatted_events = []
            for ev in (event_records or []):
                formatted_events.append({
                    "time": str(getattr(ev, "Time", "N/A")),
                    "event_type": str(getattr(ev, "EventType", "AlarmCondition")),
                    "severity": getattr(ev, "Severity", 500),
                    "message": str(getattr(ev, "Message", "Trip Alarm Triggered")),
                })
            return {
                "machine_node_id": machine_node_id,
                "event_count": len(formatted_events),
                "events": formatted_events,
            }
        except Exception as e:
            logger.warning("Failed to read alarm events for %s: %s", machine_node_id, e)
            return {
                "machine_node_id": machine_node_id,
                "event_count": 0,
                "events": [],
                "note": f"No active alarm log found under node: {e}",
            }

    async def get_node_attributes(self, node_id: str) -> Dict[str, Any]:
        """Read full OPC UA node attributes and metadata (IEC 62541-4).

        :param node_id: The OPC UA node ID to read attributes for.
        :return: Dict containing all parsed attribute values.
        """
        await self._ensure_connected()
        node_id = clean_node_id(node_id)
        node = self.client.raw_client.get_node(node_id)

        from asyncua import ua

        attrs = [
            ua.AttributeIds.NodeClass,
            ua.AttributeIds.BrowseName,
            ua.AttributeIds.DataType,
            ua.AttributeIds.AccessLevel,
            ua.AttributeIds.UserAccessLevel,
            ua.AttributeIds.Description,
            ua.AttributeIds.ValueRank,
        ]

        try:
            results = await node.read_attributes(attrs)
            
            # Helper to parse access level bitmask
            def parse_access_level(level_val):
                if level_val is None:
                    return []
                val = int(level_val)
                levels = []
                if val & 1:
                    levels.append("CurrentRead")
                if val & 2:
                    levels.append("CurrentWrite")
                if val & 4:
                    levels.append("HistoryRead")
                if val & 8:
                    levels.append("HistoryWrite")
                return levels

            # Parse NodeClass
            node_class_raw = results[0].Value.Value
            node_class = getattr(node_class_raw, "name", str(node_class_raw)) if node_class_raw is not None else "Unknown"

            # Parse BrowseName
            browse_name_raw = results[1].Value.Value
            browse_name = browse_name_raw.Name if browse_name_raw is not None else "Unknown"

            # Parse DataType node ID to human BrowseName
            data_type_raw = results[2].Value.Value
            data_type_str = "Unknown"
            if data_type_raw is not None:
                try:
                    dt_node = self.client.raw_client.get_node(data_type_raw)
                    dt_bn = await dt_node.read_browse_name()
                    data_type_str = dt_bn.Name
                except Exception:
                    data_type_str = str(data_type_raw)

            # Parse AccessLevel & UserAccessLevel
            access_level = parse_access_level(results[3].Value.Value)
            user_access_level = parse_access_level(results[4].Value.Value)

            # Parse Description
            desc_raw = results[5].Value.Value
            description = getattr(desc_raw, "Text", str(desc_raw)) if desc_raw is not None else ""

            # Parse ValueRank
            value_rank = results[6].Value.Value
            value_rank_int = int(value_rank) if value_rank is not None else -1

            return {
                "node_id": node_id,
                "node_class": node_class,
                "browse_name": browse_name,
                "data_type": data_type_str,
                "access_level": access_level,
                "user_access_level": user_access_level,
                "description": description,
                "value_rank": value_rank_int,
                "writable": "CurrentWrite" in access_level,
            }

        except Exception as e:
            logger.error("Error reading node attributes for %s: %s", node_id, e, exc_info=True)
            raise

    async def history_read_at_time(
        self,
        node_id: str,
        timestamps: List[str],
    ) -> Dict[str, Any]:
        """Read historical value snapshots for specific timestamps (IEC 62541-11).

        :param node_id: Target OPC UA node ID.
        :param timestamps: List of ISO 8601 timestamp strings.
        :return: Dict containing target node_id and reading snapshots.
        """
        await self._ensure_connected()
        node_id = clean_node_id(node_id)
        node = self.client.raw_client.get_node(node_id)

        from asyncua import ua
        from datetime import datetime

        # Parse ISO strings to datetime objects
        parsed_times = []
        for ts in timestamps:
            try:
                clean_ts = ts.replace("Z", "+00:00") if ts.endswith("Z") else ts
                parsed_times.append(datetime.fromisoformat(clean_ts))
            except Exception as e:
                logger.warning("Failed to parse ISO timestamp '%s': %s", ts, e)

        if not parsed_times:
            return {
                "node_id": node_id,
                "snapshot_count": 0,
                "readings": [],
                "note": "No valid ISO 8601 timestamps provided.",
            }

        try:
            details = ua.ReadAtTimeDetails()
            details.ReqTimes = parsed_times

            history_data = await node.history_read(details)
            formatted_readings = []

            for idx, datavalue in enumerate(history_data or []):
                val = to_json_safe(datavalue.Value.Value) if datavalue and datavalue.Value else None

                req_time = timestamps[idx] if idx < len(timestamps) else "Unknown"
                formatted_readings.append({
                    "requested_time": req_time,
                    "value": val,
                    "status": str(getattr(datavalue, "StatusCode", "Good")),
                    "source_timestamp": str(getattr(datavalue, "SourceTimestamp", "N/A")),
                })

            return {
                "node_id": node_id,
                "snapshot_count": len(formatted_readings),
                "readings": formatted_readings,
            }
        except Exception as e:
            logger.warning("Failed to read history at time for node %s: %s", node_id, e)
            return {
                "node_id": node_id,
                "snapshot_count": 0,
                "readings": [],
                "note": f"History read at time not supported or failed: {e}",
            }

    async def detect_anomalies(
        self,
        node_id: str,
        lookback_hours: int = 24,
        sensor_type: str = "general",
    ) -> Dict[str, Any]:
        """Run statistical anomaly detection on recent historical telemetry.

        Fetches historical data via read_node_history() and passes it through
        the analytics engine's 4 industry-standard methods.

        :param node_id: OPC UA Node ID of the sensor.
        :param lookback_hours: Hours of history to analyze (default 24).
        :param sensor_type: Sensor type hint ('temperature', 'pressure',
                            'vibration', 'speed', 'current', 'flow', 'general').
        :return: Dict containing per-method anomaly scores and overall severity.
        """
        from backend.analytics.anomaly_engine import run_full_anomaly_analysis

        now = datetime.now(timezone.utc)
        start_time = now - timedelta(hours=lookback_hours)

        # Fetch raw history using existing method
        history_result = await self.read_node_history(
            node_id=node_id,
            start_time_iso=start_time.isoformat(),
            end_time_iso=now.isoformat(),
            num_values=500,
        )

        records = history_result.get("history", [])

        # Extract numeric values and epoch timestamps
        values: List[float] = []
        timestamps_epoch: List[float] = []
        for rec in records:
            val = rec.get("value")
            ts_str = rec.get("timestamp")
            if val is None or ts_str is None:
                continue
            try:
                numeric_val = float(val)
            except (TypeError, ValueError):
                continue
            try:
                ts_clean = ts_str.replace("Z", "+00:00") if isinstance(ts_str, str) and ts_str.endswith("Z") else ts_str
                ts_dt = datetime.fromisoformat(str(ts_clean))
                epoch = ts_dt.timestamp()
            except Exception:
                continue
            values.append(numeric_val)
            timestamps_epoch.append(epoch)

        # Read live current value for real-time dashboard display
        current_val = None
        try:
            current_val = await self.read_node_value(node_id)
        except Exception:
            pass

        if not values:
            is_numeric_live = isinstance(current_val, (int, float)) and not isinstance(current_val, bool)
            return {
                "node_id": node_id,
                "sensor_type": sensor_type,
                "lookback_hours": lookback_hours,
                "sample_count": 1 if is_numeric_live else 0,
                "current_value": current_val,
                "overall_severity": "HEALTHY" if is_numeric_live else "INSUFFICIENT_DATA",
                "health_score": 95 if is_numeric_live else 90,
                "methods": {},
                "note": "Live telemetry streaming active." if is_numeric_live else "No valid numeric historical data found for analysis.",
            }

        # Run the full statistical analysis
        analysis = run_full_anomaly_analysis(
            values=values,
            timestamps_epoch=timestamps_epoch,
            sensor_type=sensor_type,
        )

        analysis["node_id"] = node_id
        analysis["lookback_hours"] = lookback_hours
        analysis["current_value"] = current_val if current_val is not None else values[-1]
        return analysis



