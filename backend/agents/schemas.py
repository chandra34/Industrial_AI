"""
Pydantic schemas for the Native Python Multi-Agent Orchestrator.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentQueryRequest(BaseModel):
    """User prompt request payload."""

    query: str = Field(..., description="Natural language question from user")
    user_role: str = Field(default="operator", description="User authorization role (e.g., operator, manager)")
    plant_id: Optional[str] = Field(default=None, description="Optional default plant ID context")
    max_steps: int = Field(default=5, ge=1, le=10, description="Max tool execution iterations")


class ToolCallRecord(BaseModel):
    """Execution log for a single tool call."""

    tool_name: str
    tool_args: Dict[str, Any]
    result: Any
    execution_time_seconds: float = 0.0


class AgentResponse(BaseModel):
    """Final synthesized response returned to the UI."""

    query: str
    answer: str
    steps_taken: int
    tool_calls: List[ToolCallRecord] = []
    llm_provider_used: str
    llm_model_used: str
