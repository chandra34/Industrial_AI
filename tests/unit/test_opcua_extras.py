import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from backend.connectors.opcua.connection import OPCUAClient
from backend.connectors.opcua.browser import OPCUABrowser
from backend.connectors.opcua.reader import OPCUAReader
from backend.connectors.opcua.subscription import OPCUASubscriptionManager
from backend.connectors.opcua.exceptions import OPCUANotConnectedError


@pytest.mark.asyncio
async def test_get_server_capabilities_mock():
    """Verify get_server_capabilities, supports_history, and supports_events mock logic."""
    client = OPCUAClient()
    
    # 1. Test error when not connected
    with pytest.raises(OPCUANotConnectedError):
        await client.get_server_capabilities()

    # 2. Mock connected raw client and capability nodes
    from asyncua.client.ua_client import UaClientState
    mock_raw_client = MagicMock()
    mock_raw_client.state = UaClientState.CONNECTED
    client._client = mock_raw_client

    # Mock the capabilities response nodes
    mock_profile_node = AsyncMock()
    mock_profile_node.read_value.return_value = [
        "http://opcfoundation.org/UA-Profile/Server/StandardUA",
        "http://opcfoundation.org/UA-Profile/Server/HistoricalRawData",
        "http://opcfoundation.org/UA-Profile/Server/AlarmsConditionServer"
    ]
    
    mock_sample_rate_node = AsyncMock()
    mock_sample_rate_node.read_value.return_value = 50.0

    mock_max_read_node = AsyncMock()
    mock_max_read_node.read_value.return_value = 500

    def get_node_side_effect(node_id):
        if "2269" in str(node_id):
            return mock_profile_node
        elif "2272" in str(node_id):
            return mock_sample_rate_node
        elif "11705" in str(node_id):
            return mock_max_read_node
        return AsyncMock()

    mock_raw_client.get_node.side_effect = get_node_side_effect

    # Fetch capabilities
    caps = await client.get_server_capabilities()

    assert caps["supports_history"] is True
    assert caps["supports_events"] is True
    assert caps["max_nodes_per_read"] == 500
    assert caps["min_supported_sample_rate_ms"] == 50.0

    assert client.supports_history is True
    assert client.supports_events is True


@pytest.mark.asyncio
async def test_translate_browse_path_mock():
    """Verify translate_browse_path successfully resolves paths to Node IDs."""
    client = MagicMock(spec=OPCUAClient)
    client.is_connected = True
    
    mock_raw_client = MagicMock()
    client.raw_client = mock_raw_client

    # Mock root objects node
    mock_objects_node = MagicMock()
    mock_objects_node.nodeid = "ns=0;i=85"
    mock_raw_client.get_objects_node.return_value = mock_objects_node

    # Mock translate response
    mock_target = MagicMock()
    mock_target.TargetId = "ns=3;i=1001"
    mock_result = MagicMock()
    mock_result.Targets = [mock_target]
    mock_raw_client.translate_browsepaths = AsyncMock(return_value=[mock_result])

    browser = OPCUABrowser(client)
    res = await browser.translate_browse_path("Objects > Simulation > Counter")

    assert res["status"] == "Success"
    assert res["node_id"] == "ns=3;i=1001"
    mock_raw_client.translate_browsepaths.assert_called_once()


@pytest.mark.asyncio
async def test_get_node_attributes_mock():
    """Verify get_node_attributes correctly reads and parses standard attributes."""
    client = MagicMock(spec=OPCUAClient)
    client.is_connected = True
    
    mock_raw_client = MagicMock()
    client.raw_client = mock_raw_client

    # Mock node and attributes response
    mock_node = AsyncMock()
    mock_raw_client.get_node.return_value = mock_node

    # Mock attribute read results
    # 0: NodeClass, 1: BrowseName, 2: DataType, 3: AccessLevel, 4: UserAccessLevel, 5: Description, 6: ValueRank
    mock_class = MagicMock()
    mock_class.name = "Variable"
    
    mock_bn = MagicMock()
    mock_bn.Name = "Counter"
    
    mock_dt_node = AsyncMock()
    mock_dt_node.read_browse_name.return_value.Name = "Int32"
    mock_raw_client.get_node.side_effect = lambda nid: mock_dt_node if "DataType" in str(nid) or "i=6" in str(nid) else mock_node

    mock_desc = MagicMock()
    mock_desc.Text = "Simulation Counter"

    mock_results = [
        MagicMock(Value=MagicMock(Value=mock_class)),  # NodeClass
        MagicMock(Value=MagicMock(Value=mock_bn)),     # BrowseName
        MagicMock(Value=MagicMock(Value="i=6")),       # DataType NodeId
        MagicMock(Value=MagicMock(Value=3)),           # AccessLevel: CurrentRead | CurrentWrite
        MagicMock(Value=MagicMock(Value=1)),           # UserAccessLevel: CurrentRead
        MagicMock(Value=MagicMock(Value=mock_desc)),   # Description
        MagicMock(Value=MagicMock(Value=-1)),          # ValueRank (Scalar)
    ]
    mock_node.read_attributes.return_value = mock_results

    reader = OPCUAReader(client)
    attrs = await reader.get_node_attributes("ns=3;i=1001")

    assert attrs["node_class"] == "Variable"
    assert attrs["browse_name"] == "Counter"
    assert "CurrentRead" in attrs["access_level"]
    assert "CurrentWrite" in attrs["access_level"]
    assert attrs["writable"] is True
    assert attrs["description"] == "Simulation Counter"
    assert attrs["value_rank"] == -1


@pytest.mark.asyncio
async def test_history_read_at_time_mock():
    """Verify history_read_at_time correctly reads values at target timestamps."""
    client = MagicMock(spec=OPCUAClient)
    client.is_connected = True
    
    mock_raw_client = MagicMock()
    client.raw_client = mock_raw_client

    mock_node = AsyncMock()
    mock_raw_client.get_node.return_value = mock_node

    # Mock historical readings response
    mock_val1 = MagicMock()
    mock_val1.Value.Value = 12.5
    mock_val1.StatusCode = "Good"
    mock_val1.SourceTimestamp = datetime(2026, 8, 8, 12, 0, 0, tzinfo=timezone.utc)

    mock_node.history_read.return_value = [mock_val1]

    reader = OPCUAReader(client)
    res = await reader.history_read_at_time("ns=3;i=1001", ["2026-08-08T12:00:00Z"])

    assert res["snapshot_count"] == 1
    assert res["readings"][0]["value"] == 12.5
    assert res["readings"][0]["status"] == "Good"


@pytest.mark.asyncio
async def test_subscription_manager_mock():
    """Verify OPCUASubscriptionManager subscribe, unsubscribe, and callback operations."""
    client = MagicMock(spec=OPCUAClient)
    client.is_connected = True
    
    mock_raw_client = MagicMock()
    client.raw_client = mock_raw_client

    # Mock raw subscription object
    mock_sub = AsyncMock()
    mock_raw_client.create_subscription = AsyncMock(return_value=mock_sub)
    mock_sub.subscribe_data_change.return_value = [42]  # handle 42

    sub_mgr = OPCUASubscriptionManager(client)

    # 1. Test data change subscription
    called = []
    def callback(node_id, val, ts):
        called.append((node_id, val))

    sub_id = await sub_mgr.subscribe(
        node_ids=["ns=3;i=1001"],
        publish_interval_ms=500,
        callback=callback
    )

    assert sub_id in sub_mgr._subscriptions
    assert sub_mgr._subscriptions[sub_id]["type"] == "data_change"

    # Simulate callback execution
    handler = mock_raw_client.create_subscription.call_args[0][1]
    mock_node = MagicMock()
    mock_node.nodeid = "ns=3;i=1001"
    
    handler.datachange_notification(mock_node, 100, MagicMock())
    assert len(called) == 1
    assert called[0] == ("ns=3;i=1001", 100)

    # 2. Test unsubscribe
    success = await sub_mgr.unsubscribe(sub_id)
    assert success is True
    mock_sub.unsubscribe.assert_called_once_with([42])
    mock_sub.delete.assert_called_once()
    assert sub_id not in sub_mgr._subscriptions


@pytest.mark.asyncio
async def test_read_multiple_nodes_mock():
    """Verify read_multiple_nodes executes native OPC UA batch reading."""
    client = MagicMock(spec=OPCUAClient)
    client.is_connected = True
    
    mock_raw_client = MagicMock()
    client.raw_client = mock_raw_client

    mock_node1 = AsyncMock()
    mock_node2 = AsyncMock()
    mock_raw_client.get_node.side_effect = lambda nid: mock_node1 if "1001" in nid else mock_node2

    mock_raw_client.read_values = AsyncMock(return_value=[42.5, 99.0])

    reader = OPCUAReader(client)
    res = await reader.read_multiple_nodes(["ns=3;i=1001", "ns=3;i=1002"])

    assert res["ns=3;i=1001"] == 42.5
    assert res["ns=3;i=1002"] == 99.0
    mock_raw_client.read_values.assert_called_once()


@pytest.mark.asyncio
async def test_read_opcua_history_at_time_tool_mock():
    """Verify read_opcua_history_at_time tool execution and guardrail whitelist authorization."""
    from backend.agents.tools_registry import read_opcua_history_at_time
    from backend.utils.guardrails import check_tool_allowed

    assert check_tool_allowed("read_opcua_history_at_time") is True

    res = await read_opcua_history_at_time("ns=3;i=1001", ["2026-08-08T12:00:00Z"])
    assert res["snapshot_count"] == 1
    assert res["readings"][0]["requested_time"] == "2026-08-08T12:00:00Z"


@pytest.mark.asyncio
async def test_get_opcua_node_attributes_tool_mock():
    """Verify get_opcua_node_attributes tool execution and guardrail authorization."""
    from backend.agents.tools_registry import get_opcua_node_attributes
    from backend.utils.guardrails import check_tool_allowed

    assert check_tool_allowed("get_opcua_node_attributes") is True

    res = await get_opcua_node_attributes("ns=3;i=1001")
    assert res["node_class"] == "Variable"
    assert res["writable"] is True



