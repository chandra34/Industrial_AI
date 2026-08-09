"""
Unit tests for the Native Python Multi-Agent Orchestrator.
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from backend.agents.schemas import AgentQueryRequest, AgentResponse
from backend.agents.orchestrator import IndustrialOrchestrator
from backend.connectors.sap import SAPClient, SAPConfig
from backend.connectors.sap.tools import check_material_stock


@pytest.mark.asyncio
async def test_agent_orchestrator_initialization():
    """Verify IndustrialOrchestrator initializes correctly."""
    config = SAPConfig(_env_file=None)
    sap_client = SAPClient(config)
    orchestrator = IndustrialOrchestrator(sap_client=sap_client, provider="openai")

    assert orchestrator.llm_provider.provider == "openai"
    assert len(orchestrator.tool_definitions) > 0


@pytest.mark.asyncio
async def test_agent_orchestrator_direct_text_response():
    """Verify orchestrator handles text response with zero tool calls."""
    config = SAPConfig(_env_file=None)
    sap_client = SAPClient(config)
    orchestrator = IndustrialOrchestrator(sap_client=sap_client, provider="openai")

    mock_unified_msg = MagicMock()
    mock_unified_msg.content = "Plant 1010 is operating normally."
    mock_unified_msg.tool_calls = None

    with patch.object(orchestrator.llm_provider, "generate_step", new=AsyncMock(return_value=(mock_unified_msg, None))):
        req = AgentQueryRequest(query="Status of plant 1010?")
        res = await orchestrator.run(req)

        assert isinstance(res, AgentResponse)
        assert res.answer == "Plant 1010 is operating normally."
        assert res.steps_taken == 1
        assert len(res.tool_calls) == 0


@pytest.mark.asyncio
async def test_agent_orchestrator_tool_execution():
    """Verify orchestrator executes tool function and returns synthesized answer."""
    config = SAPConfig(_env_file=None)
    sap_client = SAPClient(config)
    orchestrator = IndustrialOrchestrator(sap_client=sap_client, provider="openai")

    # Step 1: LLM returns tool call request for check_material_stock
    mock_tc = MagicMock()
    mock_tc.name = "check_material_stock"
    mock_tc.arguments = {"material_id": "SKF-6214", "plant_id": "1010"}
    mock_tc.id = "call_test_123"

    mock_step1_msg = MagicMock()
    mock_step1_msg.content = None
    mock_step1_msg.tool_calls = [mock_tc]

    # Step 2: LLM returns final text answer after tool execution
    mock_step2_msg = MagicMock()
    mock_step2_msg.content = "Plant 1010 has 15 SKF-6214 bearings available in stock."
    mock_step2_msg.tool_calls = None

    mock_tool_func = AsyncMock(return_value=[{"Material": "SKF-6214", "Stock": 15}])

    with patch.object(orchestrator.llm_provider, "generate_step", side_effect=[(mock_step1_msg, MagicMock()), (mock_step2_msg, MagicMock())]):
        with patch.dict("backend.agents.orchestrator.ALL_EXECUTABLE_TOOLS", {"check_material_stock": mock_tool_func}):
            req = AgentQueryRequest(query="Do we have SKF-6214 bearings in stock?")
            res = await orchestrator.run(req)

            assert res.steps_taken == 2
            assert "15 SKF-6214 bearings" in res.answer
            assert len(res.tool_calls) == 1
            assert res.tool_calls[0].tool_name == "check_material_stock"


@pytest.mark.asyncio
async def test_gemini_multi_tool_response_merging():
    """Verify LLMProvider merges consecutive tool response messages into a single Gemini user turn."""
    from backend.agents.llm_provider import LLMProvider

    provider = LLMProvider(provider="gemini", model="gemini-2.5-flash")

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Check stock and live temperature."},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"name": "check_material_stock", "arguments": {"material_id": "SKF-6214"}},
                {"name": "read_opcua_node_value", "arguments": {"node_id": "ns=2;i=1001"}},
            ],
        },
        {"role": "tool", "name": "check_material_stock", "content": '{"stock": 15}'},
        {"role": "tool", "name": "read_opcua_node_value", "content": '{"value": 87.5}'},
    ]

    mock_client = MagicMock()
    mock_api_client = AsyncMock()
    mock_api_client.async_request.return_value = {
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [{"text": "Stock is 15 and temperature is 87.5."}],
                }
            }
        ]
    }
    mock_client._api_client = mock_api_client

    with patch("google.genai.Client", return_value=mock_client):
        unified_msg, response_dict = await provider.generate_step(messages, tools=[])

        # Verify async_request was called
        assert mock_api_client.async_request.called
        call_args = mock_api_client.async_request.call_args[0]
        request_dict = call_args[2]

        contents = request_dict["contents"]
        # Expect 3 turns: user prompt, model assistant turn, merged user tool responses turn
        assert len(contents) == 3
        assert contents[0]["role"] == "user"
        assert contents[1]["role"] == "model"
        assert contents[2]["role"] == "user"

        # Verify that the merged user turn contains BOTH functionResponse parts
        parts = contents[2]["parts"]
        assert len(parts) == 2
        assert "functionResponse" in parts[0]
        assert parts[0]["functionResponse"]["name"] == "check_material_stock"
        assert "functionResponse" in parts[1]
        assert parts[1]["functionResponse"]["name"] == "read_opcua_node_value"


def test_tool_schema_signature_alignment():
    """Verify tool definitions contain all required filter parameters."""
    from backend.agents.tools_registry import get_openai_tool_definitions

    schemas = {
        t["function"]["name"]: t["function"]["parameters"]["properties"]
        for t in get_openai_tool_definitions()
    }

    assert "notification_type" in schemas["get_maintenance_notifications"]
    assert "status" in schemas["get_production_orders"]


@pytest.mark.asyncio
async def test_tool_execution_signature_filtering():
    """Verify _execute_single_tool filters out hallucinated kwargs before calling target function."""
    config = SAPConfig(_env_file=None)
    sap_client = SAPClient(config)
    orchestrator = IndustrialOrchestrator(sap_client=sap_client, provider="openai")

    mock_tc = MagicMock()
    mock_tc.name = "check_material_stock"
    # Pass valid kwargs + a hallucinated 'invalid_param'
    mock_tc.arguments = {"material_id": "SKF-6214", "plant_id": "1010", "invalid_param": "hallucinated_val"}
    mock_tc.id = "call_test_sig"

    called_kwargs = {}

    async def mock_tool_func(client, material_id: str, plant_id: str):
        called_kwargs["material_id"] = material_id
        called_kwargs["plant_id"] = plant_id
        return [{"Material": material_id, "Stock": 10}]

    with patch.dict("backend.agents.orchestrator.ALL_EXECUTABLE_TOOLS", {"check_material_stock": mock_tool_func}):
        rec, msg_out = await orchestrator._execute_single_tool(mock_tc, user_id="test_user")

        assert "error" not in rec.result
        # Ensure target function was called WITHOUT 'invalid_param'
        assert "invalid_param" not in called_kwargs
        assert called_kwargs["material_id"] == "SKF-6214"
        assert called_kwargs["plant_id"] == "1010"


@pytest.mark.asyncio
async def test_tool_execution_timeout_protection():
    """Verify _execute_single_tool returns a timeout error dict when tool execution exceeds timeout limit."""
    config = SAPConfig(_env_file=None)
    sap_client = SAPClient(config)
    orchestrator = IndustrialOrchestrator(sap_client=sap_client, provider="openai")

    mock_tc = MagicMock()
    mock_tc.name = "read_opcua_node_value"
    mock_tc.arguments = {"node_id": "ns=2;i=1001"}
    mock_tc.id = "call_test_timeout"

    # Define a slow function that sleeps longer than timeout
    async def slow_func(node_id: str, opcua_client=None):
        import asyncio
        await asyncio.sleep(0.5)
        return {"value": 100}

    with patch.dict("backend.agents.orchestrator.ALL_EXECUTABLE_TOOLS", {"read_opcua_node_value": slow_func}):
        rec, msg_out = await orchestrator._execute_single_tool(mock_tc, user_id="test_user", timeout_seconds=0.1)

        assert "error" in rec.result
        assert "timed out after 0.1 seconds" in rec.result["error"]


@pytest.mark.asyncio
async def test_parallel_tool_concurrent_execution():
    """Verify orchestrator runs multiple requested tool calls in parallel concurrently."""
    config = SAPConfig(_env_file=None)
    sap_client = SAPClient(config)
    orchestrator = IndustrialOrchestrator(sap_client=sap_client, provider="openai")

    mock_tc1 = MagicMock()
    mock_tc1.name = "tool1"
    mock_tc1.arguments = {}
    mock_tc1.id = "call_1"

    mock_tc2 = MagicMock()
    mock_tc2.name = "tool2"
    mock_tc2.arguments = {}
    mock_tc2.id = "call_2"

    mock_msg1 = MagicMock()
    mock_msg1.content = None
    mock_msg1.tool_calls = [mock_tc1, mock_tc2]

    mock_msg2 = MagicMock()
    mock_msg2.content = "Done parallel tools."
    mock_msg2.tool_calls = None

    import asyncio
    async def slow_tool1():
        await asyncio.sleep(0.2)
        return {"tool": 1}

    async def slow_tool2():
        await asyncio.sleep(0.2)
        return {"tool": 2}

    with patch.object(orchestrator.llm_provider, "generate_step", side_effect=[(mock_msg1, {}), (mock_msg2, {})]):
        with patch.dict("backend.agents.orchestrator.ALL_EXECUTABLE_TOOLS", {"tool1": slow_tool1, "tool2": slow_tool2}):
            t0 = time.time()
            res = await orchestrator.run(AgentQueryRequest(query="Run 2 tools in parallel"))
            t_total = time.time() - t0

            assert len(res.tool_calls) == 2
            # If run concurrently, total time should be ~0.2s, not 0.4s
            assert t_total < 0.35



