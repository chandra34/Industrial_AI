"""
Core Native Python Industrial Multi-Agent Orchestrator.
"""

import time
import json
import inspect
import logging
from typing import Any, Dict, List, Optional

from backend.connectors.sap import SAPClient
from backend.connectors.opcua import OPCUAClient
from backend.agents.schemas import AgentQueryRequest, AgentResponse, ToolCallRecord
from backend.agents.prompts import SYSTEM_PROMPT
from backend.agents.tools_registry import ALL_EXECUTABLE_TOOLS, get_openai_tool_definitions
from backend.agents.llm_provider import LLMProvider

logger = logging.getLogger(__name__)


class IndustrialOrchestrator:
    """Native Python Async Tool Loop Orchestrator."""

    def __init__(
        self,
        sap_client: SAPClient,
        opcua_client: Optional[OPCUAClient] = None,
        retrieval_service: Optional[Any] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """Initialize the Industrial Orchestrator.

        :param sap_client: Connected SAPClient instance.
        :param opcua_client: Optional OPCUAClient instance.
        :param retrieval_service: Optional RetrievalService instance for RAG search.
        :param provider: LLM provider string ('openai' or 'gemini').
        :param model: LLM model string.
        """
        self.sap_client = sap_client
        self.opcua_client = opcua_client
        self.retrieval_service = retrieval_service
        self.llm_provider = LLMProvider(provider=provider, model=model)
        self.tool_definitions = get_openai_tool_definitions()

    async def run(self, request: AgentQueryRequest) -> AgentResponse:
        """Run the native async tool call loop.

        :param request: AgentQueryRequest object containing user prompt and config.
        :return: AgentResponse object with final text answer and execution log.
        """
        start_time = time.time()
        tool_records: List[ToolCallRecord] = []

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": request.query},
        ]

        for step in range(request.max_steps):
            logger.info("Orchestrator Step %d/%d for query: '%s'", step + 1, request.max_steps, request.query)
            unified_msg, raw_msg = await self.llm_provider.generate_step(
                messages, self.tool_definitions
            )

            # If no tool calls requested, we have reached the final text answer
            if not unified_msg.tool_calls:
                logger.info("Orchestrator completed synthesis in %d step(s).", step + 1)
                return AgentResponse(
                    query=request.query,
                    answer=unified_msg.content or "No response generated.",
                    steps_taken=step + 1,
                    tool_calls=tool_records,
                    llm_provider_used=self.llm_provider.provider,
                    llm_model_used=self.llm_provider.model,
                )

            # Append assistant message with tool call
            if self.llm_provider.provider == "openai":
                messages.append(raw_msg)
            else:
                messages.append({"role": "assistant", "content": unified_msg.content})

            # Execute each requested tool
            for tc in unified_msg.tool_calls:
                t_start = time.time()
                tool_name = tc.name
                tool_args = tc.arguments

                logger.info("Executing tool '%s' with args %s", tool_name, tool_args)

                try:
                    if tool_name in ALL_EXECUTABLE_TOOLS:
                        func = ALL_EXECUTABLE_TOOLS[tool_name]
                        # Signature inspection: pass client or retrieval_service if tool expects parameter
                        sig = inspect.signature(func)
                        kwargs = dict(tool_args)
                        if "client" in sig.parameters:
                            kwargs["client"] = self.sap_client
                        if "retrieval_service" in sig.parameters:
                            kwargs["retrieval_service"] = self.retrieval_service
                        result = await func(**kwargs)
                    else:
                        result = {"error": f"Tool '{tool_name}' not found."}
                except Exception as e:
                    logger.error("Error executing tool %s: %s", tool_name, e, exc_info=True)
                    result = {"error": str(e)}

                t_elapsed = time.time() - t_start
                tool_records.append(
                    ToolCallRecord(
                        tool_name=tool_name,
                        tool_args=tool_args,
                        result=result,
                        execution_time_seconds=round(t_elapsed, 4),
                    )
                )

                # Append tool execution result back to conversation
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                })

        return AgentResponse(
            query=request.query,
            answer="Max step limit reached before final synthesis.",
            steps_taken=request.max_steps,
            tool_calls=tool_records,
            llm_provider_used=self.llm_provider.provider,
            llm_model_used=self.llm_provider.model,
        )
