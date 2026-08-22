"""
OPCUA Subscription Manager for managing data change and event subscriptions.

Provides long-running subscription tasks, monitored item change handlers,
and alarm condition event listeners.
"""

import uuid
import logging
from typing import Any, Dict, List, Callable, Optional
from datetime import datetime, timezone

from backend.connectors.opcua.connection import OPCUAClient
from backend.connectors.opcua.exceptions import OPCUANotConnectedError
from backend.connectors.opcua.utils import clean_node_id

logger = logging.getLogger(__name__)


class _DataChangeHandler:
    """Internal handler for OPC UA data change notifications."""

    def __init__(self, callback: Callable[[str, Any, datetime], None]) -> None:
        self._callback = callback

    def datachange_notification(self, node: Any, val: Any, data: Any) -> None:
        """Called by asyncua when a monitored node value changes.

        :param node: asyncua Node object.
        :param val: The new value.
        :param data: The MonitoredItemNotification object containing metadata.
        """
        try:
            node_id_str = str(node.nodeid)
            clean_id = clean_node_id(node_id_str)
            
            # Extract timestamp from notification data if available, fallback to now
            timestamp = datetime.now(timezone.utc)
            if hasattr(data, "monitored_item"):
                # some versions of asyncua wrap it this way
                pass
            if hasattr(data, "value") and data.value is not None:
                source_time = getattr(data.value, "SourceTimestamp", None) or getattr(data.value, "ServerTimestamp", None)
                if isinstance(source_time, datetime):
                    timestamp = source_time

            # Call the user-provided callback
            self._callback(clean_id, val, timestamp)
        except Exception as e:
            logger.error("Error executing data change subscription callback: %s", e, exc_info=True)


class _EventHandler:
    """Internal handler for OPC UA event notifications."""

    def __init__(
        self,
        callback: Callable[[Dict[str, Any]], None],
        async_handler: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ) -> None:
        self._callback = callback
        self._async_handler = async_handler

    def event_notification(self, event: Any) -> None:
        """Called by asyncua when an event fires.

        :param event: The Event object containing event fields.
        """
        try:
            # Extract standard event attributes
            event_dict = {
                "time": str(getattr(event, "Time", datetime.now(timezone.utc))),
                "event_type": str(getattr(event, "EventType", "BaseEventType")),
                "severity": int(getattr(event, "Severity", 500)),
                "message": str(getattr(event, "Message", "Event Triggered")),
                "source_name": str(getattr(event, "SourceName", "OPCUA Server")),
            }
            # Execute synchronous callback
            self._callback(event_dict)

            # If async handler provided and event is high severity (Trip / Alarm), schedule in event loop
            if self._async_handler and event_dict["severity"] >= 500:
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._async_handler(event_dict))
                except RuntimeError:
                    pass
        except Exception as e:
            logger.error("Error executing event subscription callback: %s", e, exc_info=True)


class OPCUASubscriptionManager:
    """Manages real-time Monitored Items and Event Subscriptions on an OPC UA server."""

    def __init__(self, client: OPCUAClient) -> None:
        """Initialize the subscription manager.

        :param client: The active OPCUAClient connection instance.
        """
        self.client = client
        self._subscriptions: Dict[str, Dict[str, Any]] = {}

    async def _ensure_connected(self) -> None:
        """Helper to verify connection before subscribing."""
        if not self.client.is_connected:
            raise OPCUANotConnectedError("Client is not connected. Connect first to manage subscriptions.")

    async def subscribe(
        self,
        node_ids: List[str],
        publish_interval_ms: int = 500,
        callback: Callable[[str, Any, datetime], None] = lambda *_: None,
    ) -> str:
        """Subscribe to live data changes on one or more node IDs.

        :param node_ids: List of OPC UA Node IDs to monitor.
        :param publish_interval_ms: Server notification interval in milliseconds.
        :param callback: Callback function: callback(node_id, value, timestamp).
        :return: A unique subscription ID string.
        """
        await self._ensure_connected()
        from asyncua import ua

        clean_ids = [clean_node_id(nid) for nid in node_ids]
        logger.info("Subscribing to data changes on nodes: %s", clean_ids)

        handler = _DataChangeHandler(callback)
        sub = await self.client.raw_client.create_subscription(publish_interval_ms, handler)

        nodes = [self.client.raw_client.get_node(nid) for nid in clean_ids]
        handles = await sub.subscribe_data_change(nodes)

        # Generate a unique ID to manage this subscription session
        sub_id = str(uuid.uuid4())
        self._subscriptions[sub_id] = {
            "subscription": sub,
            "handles": handles,
            "type": "data_change",
            "nodes": clean_ids,
        }

        return sub_id

    async def subscribe_events(
        self,
        machine_node_id: str,
        publish_interval_ms: int = 500,
        callback: Callable[[Dict[str, Any]], None] = lambda *_: None,
        event_type_node_id: Optional[str] = None,
        async_handler: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ) -> str:
        """Subscribe to live trip alarms and safety events under a machine node.

        :param machine_node_id: The OPC UA node ID of the machine folder/object.
        :param publish_interval_ms: Notification check interval in milliseconds.
        :param callback: Callback function: callback(event_dict).
        :param event_type_node_id: Specific event type Node ID (default BaseEventType).
        :param async_handler: Optional async callback for high-severity alarm event handling.
        :return: A unique subscription ID string.
        """
        await self._ensure_connected()
        from asyncua import ua

        clean_machine_id = clean_node_id(machine_node_id)
        logger.info("Subscribing to alarm events under node: %s", clean_machine_id)

        handler = _EventHandler(callback, async_handler=async_handler)
        sub = await self.client.raw_client.create_subscription(publish_interval_ms, handler)

        machine_node = self.client.raw_client.get_node(clean_machine_id)
        
        # Determine the event type node to filter by
        if event_type_node_id:
            event_type_node = self.client.raw_client.get_node(clean_node_id(event_type_node_id))
        else:
            # Default to BaseEventType (ns=0;i=2041)
            event_type_node = self.client.raw_client.get_node("ns=0;i=2041")

        handle = await sub.subscribe_events(machine_node, event_type_node)

        # Store handles in a list for uniform cleanup
        sub_id = str(uuid.uuid4())
        self._subscriptions[sub_id] = {
            "subscription": sub,
            "handles": [handle],
            "type": "events",
            "node": clean_machine_id,
        }

        return sub_id

    async def unsubscribe(self, subscription_id: str) -> bool:
        """Clean up and close an active subscription handler.

        :param subscription_id: The UUID subscription ID returned by subscribe().
        :return: True if successfully unsubscribed, False if subscription ID not found.
        """
        sub_data = self._subscriptions.get(subscription_id)
        if not sub_data:
            logger.warning("Unsubscribe called for invalid or expired ID: %s", subscription_id)
            return False

        try:
            sub = sub_data["subscription"]
            handles = sub_data["handles"]
            
            # Unsubscribe handles
            if sub_data["type"] == "data_change":
                await sub.unsubscribe(handles)
            elif sub_data["type"] == "events":
                # For event subscriptions, the handle is a single element
                if isinstance(handles, list):
                    for h in handles:
                        await sub.unsubscribe(h)
                else:
                    await sub.unsubscribe(handles)

            # Delete the subscription on the server
            await sub.delete()
            logger.info("Successfully closed subscription session: %s", subscription_id)
        except Exception as e:
            logger.warning("Error closing subscription %s: %s", subscription_id, e)
        finally:
            self._subscriptions.pop(subscription_id, None)

        return True

    async def unsubscribe_all(self) -> int:
        """Close all active subscription sessions.

        :return: Count of closed subscriptions.
        """
        count = 0
        active_ids = list(self._subscriptions.keys())
        for sub_id in active_ids:
            success = await self.unsubscribe(sub_id)
            if success:
                count += 1
        return count
