"""
Unit tests for the OPC UA Connection Manager (backend/connectors/opcua/client.py).
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from backend.connectors.opcua.connection import OPCUAClient
from backend.connectors.opcua.config import OPCUAConfig
from backend.connectors.opcua.exceptions import (
    OPCUAAuthenticationError,
    OPCUAConnectionError,
    OPCUANotConnectedError,
    OPCUATimeoutError,
)


def test_opcua_config_defaults():
    """Verify OPCUAConfig default values."""
    config = OPCUAConfig()
    assert config.endpoint_url == "opc.tcp://localhost:4840"
    assert config.timeout_seconds == 4.0
    assert config.username is None
    assert config.password is None
    assert config.auto_reconnect is True
    assert config.reconnect_max_delay == 30.0
    assert config.session_name == "IndustrialAI_OPCUA_Client"


def test_opcua_client_unconnected_access():
    """Verify raw_client raises OPCUANotConnectedError when client is not connected."""
    client_mgr = OPCUAClient()
    assert client_mgr.is_connected is False

    with pytest.raises(OPCUANotConnectedError):
        _ = client_mgr.raw_client


@pytest.mark.asyncio
async def test_opcua_client_missing_asyncua():
    """Verify OPCUAConnectionError is raised with descriptive message if asyncua is missing."""
    with patch.dict(sys.modules, {"asyncua": None, "asyncua.ua.uaerrors._base": None}):
        client_mgr = OPCUAClient()
        with pytest.raises(OPCUAConnectionError) as exc_info:
            await client_mgr.connect()
        assert "asyncua" in str(exc_info.value)


@pytest.mark.asyncio
async def test_opcua_client_successful_connection():
    """Verify successful OPCUAClient connection and context manager lifecycle."""
    mock_asyncua = MagicMock()
    mock_client_inst = MagicMock()
    mock_client_inst.connect = AsyncMock()
    mock_client_inst.disconnect = AsyncMock()
    mock_client_inst.set_security_string = AsyncMock()
    
    mock_asyncua.Client.return_value = mock_client_inst
    mock_asyncua.client.ua_client.UaClientState.CONNECTED = "CONNECTED"
    mock_client_inst.state = "CONNECTED"

    with patch.dict(sys.modules, {
        "asyncua": mock_asyncua,
        "asyncua.client.ua_client": mock_asyncua.client.ua_client,
        "asyncua.ua.uaerrors._base": MagicMock(),
    }):
        config = OPCUAConfig(username="user1", password="secret_password")
        client_mgr = OPCUAClient(config)

        async with client_mgr:
            assert client_mgr.is_connected is True
            assert client_mgr.raw_client == mock_client_inst
            mock_client_inst.set_user.assert_called_once_with("user1")
            mock_client_inst.set_password.assert_called_once_with("secret_password")
            mock_client_inst.connect.assert_called_once()

        mock_client_inst.disconnect.assert_called_once()
        assert client_mgr.is_connected is False


@pytest.mark.asyncio
async def test_opcua_client_connection_refused():
    """Verify OPCUAConnectionError is raised when connection is refused."""
    mock_asyncua = MagicMock()
    mock_client_inst = MagicMock()
    mock_client_inst.connect = AsyncMock(side_effect=ConnectionRefusedError("Refused"))
    mock_asyncua.Client.return_value = mock_client_inst

    with patch.dict(sys.modules, {
        "asyncua": mock_asyncua,
        "asyncua.ua.uaerrors._base": MagicMock(),
    }):
        client_mgr = OPCUAClient()
        with pytest.raises(OPCUAConnectionError) as exc_info:
            await client_mgr.connect()

        assert "Connection refused" in str(exc_info.value)
