from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.agents.schemas import AgentResponse, ToolCallRecord
from backend.api.auth import get_current_user, FirebaseUser
from backend.api.dependencies import get_industrial_orchestrator
from backend.main import app


@pytest.fixture
def mock_user():
    return FirebaseUser(uid="test_user_123", email="operator@plant.com")


@pytest.fixture
def mock_orchestrator():
    orchestrator = MagicMock()
    mock_response = AgentResponse(
        query="Status of SKF-6214 bearing in plant 1010?",
        answer="Plant 1010 has 15 SKF-6214 bearings in stock.",
        steps_taken=2,
        tool_calls=[
            ToolCallRecord(
                tool_name="check_material_stock",
                tool_args={"material_id": "SKF-6214", "plant_id": "1010"},
                result=[{"Material": "SKF-6214", "Stock": 15}],
                execution_time_seconds=0.15,
            )
        ],
        llm_provider_used="openai",
        llm_model_used="gpt-4o",
    )
    orchestrator.run = AsyncMock(return_value=mock_response)
    return orchestrator


def test_agent_route_unauthenticated():
    """Verify endpoint rejects requests missing Authorization headers."""
    client = TestClient(app)
    response = client.post(
        "/api/v1/agent/query",
        json={"query": "Status of SKF-6214?"},
    )
    assert response.status_code == 401


def test_agent_route_success(mock_user, mock_orchestrator):
    """Verify authenticated POST /api/v1/agent/query calls orchestrator and returns AgentResponse."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_industrial_orchestrator] = lambda: mock_orchestrator

    try:
        client = TestClient(app)
        payload = {
            "query": "Status of SKF-6214 bearing in plant 1010?",
            "user_role": "operator",
            "plant_id": "1010",
            "max_steps": 5,
        }
        response = client.post("/api/v1/agent/query", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "Status of SKF-6214 bearing in plant 1010?"
        assert "15 SKF-6214 bearings" in data["answer"]
        assert data["steps_taken"] == 2
        assert len(data["tool_calls"]) == 1
        assert data["tool_calls"][0]["tool_name"] == "check_material_stock"
        assert data["llm_provider_used"] == "openai"
    finally:
        app.dependency_overrides.clear()
