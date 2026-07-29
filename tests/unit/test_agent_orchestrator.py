"""
Unit tests for the Native Python Multi-Agent Orchestrator.
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from backend.agents.schemas import AgentQueryRequest, AgentResponse
from backend.agents.orchestrator import IndustrialOrchestrator
from backend.connectors.sap import SAPClient, SAPConfig


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
