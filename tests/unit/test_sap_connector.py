"""
Unit tests for the SAP ERP Connector (backend/connectors/sap/).
"""

from unittest.mock import AsyncMock
import pytest
import httpx

from backend.connectors.sap.client import SAPClient
from backend.connectors.sap.config import SAPConfig
from backend.connectors.sap.exceptions import (
    SAPAuthenticationError,
    SAPNotConnectedError,
    SAPNotFoundError,
    SAPAPIError,
)
from backend.connectors.sap.tools import (
    ALL_SAP_TOOLS,
    get_equipment_details,
    check_material_stock,
    get_production_orders,
    get_inspection_lots,
)


# --- Config Tests ---

def test_sap_config_defaults(monkeypatch):
    """Verify SAPConfig loads with sensible defaults."""
    monkeypatch.delenv("SAP_AUTH_TYPE", raising=False)
    monkeypatch.delenv("SAP_SAP_CLIENT", raising=False)
    monkeypatch.delenv("SAP_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("SAP_MAX_RETRIES", raising=False)
    config = SAPConfig(_env_file=None)
    assert config.auth_type == "basic"
    assert config.sap_client == "100"
    assert config.timeout_seconds == 30.0
    assert config.max_retries == 3


def test_sap_config_env_loading(monkeypatch):
    """Verify SAPConfig reads from SAP_ prefixed environment variables."""
    monkeypatch.setenv("SAP_BASE_URL", "https://sap.tata.com")
    monkeypatch.setenv("SAP_AUTH_TYPE", "basic")
    monkeypatch.setenv("SAP_USERNAME", "sap_service_user")
    monkeypatch.setenv("SAP_PASSWORD", "sap_secret_pass")
    monkeypatch.setenv("SAP_SAP_CLIENT", "200")

    config = SAPConfig(_env_file=None)
    assert config.base_url == "https://sap.tata.com"
    assert config.username == "sap_service_user"
    assert config.password.get_secret_value() == "sap_secret_pass"
    assert config.sap_client == "200"


# --- Client Lifecycle Tests ---

def test_sap_client_not_connected():
    """Verify is_connected returns False before connect() is called."""
    client = SAPClient()
    assert client.is_connected is False


@pytest.mark.asyncio
async def test_sap_client_connect_basic_auth_missing():
    """Verify SAPAuthenticationError when Basic Auth credentials are missing."""
    config = SAPConfig(auth_type="basic", username=None, password=None, _env_file=None)
    client = SAPClient(config)
    with pytest.raises(SAPAuthenticationError, match="SAP_USERNAME"):
        await client.connect()


@pytest.mark.asyncio
async def test_sap_client_context_manager():
    """Verify async context manager creates and closes the httpx session."""
    config = SAPConfig(
        base_url="https://mock-sap.example.com",
        auth_type="basic",
        username="user",
        password="pass",
        _env_file=None,
    )
    async with SAPClient(config) as client:
        assert client.is_connected is True

    assert client.is_connected is False


# --- OData Query Tests ---

@pytest.mark.asyncio
async def test_sap_odata_query_not_connected():
    """Verify SAPNotConnectedError when querying without connecting first."""
    client = SAPClient()
    # Mock connect to do nothing, leaving self._client as None
    client.connect = AsyncMock()
    with pytest.raises(SAPNotConnectedError):
        await client.execute_odata_query(
            service_path="/sap/opu/odata/sap/API_EQUIPMENT",
            entity_set="Equipment",
        )


@pytest.mark.asyncio
async def test_sap_odata_query_success():
    """Verify successful OData query returns parsed JSON."""
    config = SAPConfig(
        base_url="https://mock-sap.example.com",
        auth_type="basic",
        username="user",
        password="pass",
        _env_file=None,
    )
    mock_response_data = {"d": {"results": [{"EquipmentID": "10004921"}]}}

    async with SAPClient(config) as client:
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.content = b'{"d":{"results":[]}}'
        mock_response.text = '{"d":{"results":[]}}'

        client._client.get = AsyncMock(return_value=mock_response)

        result = await client.execute_odata_query(
            service_path="/sap/opu/odata/sap/API_EQUIPMENT",
            entity_set="Equipment",
            filter_expr="MaintenancePlant eq '1010'",
            top=10,
        )
        assert "d" in result
        assert result["d"]["results"][0]["EquipmentID"] == "10004921"


@pytest.mark.asyncio
async def test_sap_odata_query_404():
    """Verify SAPNotFoundError raised on HTTP 404."""
    config = SAPConfig(
        base_url="https://mock-sap.example.com",
        auth_type="basic",
        username="user",
        password="pass",
        _env_file=None,
    )

    async with SAPClient(config) as client:
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        client._client.get = AsyncMock(return_value=mock_response)

        with pytest.raises(SAPNotFoundError):
            await client.execute_odata_query(
                service_path="/sap/opu/odata/sap/API_EQUIPMENT",
                entity_set="Equipment",
                key="'INVALID_ID'",
            )


# --- Tool Function Tests ---

@pytest.mark.asyncio
async def test_sap_tools_registry():
    """Verify ALL_SAP_TOOLS exports all 10 universal tool functions."""
    assert len(ALL_SAP_TOOLS) == 10
    assert "get_equipment_details" in ALL_SAP_TOOLS
    assert "check_material_stock" in ALL_SAP_TOOLS
    assert "get_production_orders" in ALL_SAP_TOOLS
    assert "get_inspection_lots" in ALL_SAP_TOOLS


@pytest.mark.asyncio
async def test_pm_tool_get_equipment_details():
    """Test get_equipment_details tool function."""
    config = SAPConfig(
        base_url="https://mock-sap.example.com",
        auth_type="basic",
        username="user",
        password="pass",
        _env_file=None,
    )
    async with SAPClient(config) as client:
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"d": {"Equipment": "10004921", "EquipmentName": "Pump"}}
        client._client.get = AsyncMock(return_value=mock_response)

        data = await get_equipment_details(client, "10004921")
        assert data["Equipment"] == "10004921"
        assert data["EquipmentName"] == "Pump"


def test_escape_odata_val():
    """Verify that escape_odata_val doubles single quotes correctly."""
    from backend.connectors.sap.client import escape_odata_val
    assert escape_odata_val("SKF-6214") == "SKF-6214"
    assert escape_odata_val("MAT'001") == "MAT''001"
    assert escape_odata_val("O'NEILL") == "O''NEILL"
    assert escape_odata_val("VALVE_3/8'") == "VALVE_3/8''"


@pytest.mark.asyncio
async def test_pm_tool_quote_escaping():
    """Verify that pm_tools functions escape quotes in parameters before executing OData query."""
    config = SAPConfig(
        base_url="https://mock-sap.example.com",
        auth_type="basic",
        username="user",
        password="pass",
        _env_file=None,
    )
    async with SAPClient(config) as client:
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"d": {"results": []}}
        mock_response.content = b'{"d":{"results":[]}}'
        mock_response.text = '{"d":{"results":[]}}'
        client._client.get = AsyncMock(return_value=mock_response)

        # Call tool with an apostrophe in parameter
        await check_material_stock(client, "MAT'001", "PL'10")

        # Verify that execute_odata_query was called with escaped single quotes
        client._client.get.assert_called_once()
        args, kwargs = client._client.get.call_args
        params = kwargs.get("params", {})
        assert params.get("$filter") == "Material eq 'MAT''001' and Plant eq 'PL''10'"
