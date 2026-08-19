"""
Core Native Python Industrial Multi-Agent Orchestrator.
"""

import asyncio
import time
import json
import inspect
import logging
from typing import Any, Dict, List, Optional, Tuple

from backend.connectors.sap import SAPClient
from backend.connectors.opcua import OPCUAClient
from backend.agents.schemas import AgentQueryRequest, AgentResponse, ToolCallRecord
from backend.agents.prompts import SYSTEM_PROMPT
from backend.agents.tools_registry import ALL_EXECUTABLE_TOOLS, get_openai_tool_definitions
from backend.agents.llm_provider import LLMProvider
from backend.utils.guardrails import check_tool_allowed

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

    async def _execute_single_tool(
        self,
        tc: Any,
        user_id: str,
        timeout_seconds: float = 15.0,
    ) -> Tuple[ToolCallRecord, Dict[str, Any]]:
        """Execute a single tool call with guardrail verification, signature filtering, and timeout protection."""
        t_start = time.time()
        tool_name = tc.name
        tool_args = tc.arguments or {}

        # Guardrail: block non-whitelisted (write/mutation) tool calls
        if not check_tool_allowed(tool_name):
            result = {
                "error": f"Guardrail: Tool '{tool_name}' is not permitted. Only read-only diagnostic tools are allowed."
            }
            t_elapsed = time.time() - t_start
            rec = ToolCallRecord(
                tool_name=tool_name,
                tool_args=tool_args,
                result=result,
                execution_time_seconds=round(t_elapsed, 4),
            )
            return rec, {
                "role": "tool",
                "tool_call_id": tc.id,
                "name": tool_name,
                "content": json.dumps(result),
            }

        logger.info("Executing tool '%s' with args %s", tool_name, tool_args)

        try:
            if tool_name in ALL_EXECUTABLE_TOOLS:
                func = ALL_EXECUTABLE_TOOLS[tool_name]
                sig = inspect.signature(func)

                # Signature inspection: pass client or retrieval_service if tool expects parameter
                kwargs = dict(tool_args)
                if "client" in sig.parameters:
                    kwargs["client"] = self.sap_client
                if "opcua_client" in sig.parameters:
                    kwargs["opcua_client"] = self.opcua_client
                if "retrieval_service" in sig.parameters:
                    kwargs["retrieval_service"] = self.retrieval_service
                if "user_id" in sig.parameters:
                    kwargs["user_id"] = user_id

                # Pillar 1: Signature Filtering (strip LLM-hallucinated kwargs)
                valid_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}

                # Pillar 2: Timeout Protection (15s max per tool)
                result = await asyncio.wait_for(
                    func(**valid_kwargs),
                    timeout=timeout_seconds,
                )
            else:
                result = {"error": f"Tool '{tool_name}' not found."}
        except asyncio.TimeoutError:
            logger.warning("Tool '%s' execution timed out after %.1f seconds.", tool_name, timeout_seconds)
            result = {"error": f"Tool '{tool_name}' execution timed out after {timeout_seconds} seconds."}
        except Exception as e:
            logger.error("Error executing tool %s: %s", tool_name, e, exc_info=True)
            result = {"error": str(e)}

        t_elapsed = time.time() - t_start
        rec = ToolCallRecord(
            tool_name=tool_name,
            tool_args=tool_args,
            result=result,
            execution_time_seconds=round(t_elapsed, 4),
        )
        tool_msg = {
            "role": "tool",
            "tool_call_id": tc.id,
            "name": tool_name,
            "content": json.dumps(result),
        }
        return rec, tool_msg

    async def run(self, request: AgentQueryRequest, user_id: str = "default_user") -> AgentResponse:
        """Run the native async tool call loop.

        :param request: AgentQueryRequest object containing user prompt and config.
        :param user_id: Authenticated user ID context string.
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
            elif self.llm_provider.provider == "anthropic":
                # Preserve Anthropic's native content block list (TextBlock + ToolUseBlock)
                # so Claude can see its own tool_use blocks in subsequent turns
                messages.append({
                    "role": "assistant",
                    "content": raw_msg.content,
                })
            else:
                # Preserve the raw content dictionary from the Gemini REST response
                # This retains the thoughtSignature required for multi-turn tool calling
                if isinstance(raw_msg, dict) and "candidates" in raw_msg and raw_msg["candidates"]:
                    messages.append(raw_msg["candidates"][0]["content"])
                else:
                    messages.append({
                        "role": "assistant",
                        "content": unified_msg.content,
                        "tool_calls": [
                            {"name": tc.name, "arguments": tc.arguments}
                            for tc in unified_msg.tool_calls
                        ] if unified_msg.tool_calls else None,
                    })

            # Pillar 3: Concurrent Parallel Tool Execution
            tasks = [
                self._execute_single_tool(tc, user_id=user_id)
                for tc in unified_msg.tool_calls
            ]
            executed_results = await asyncio.gather(*tasks)

            for rec, tool_msg in executed_results:
                tool_records.append(rec)
                messages.append(tool_msg)

        return AgentResponse(
            query=request.query,
            answer="Max step limit reached before final synthesis.",
            steps_taken=request.max_steps,
            tool_calls=tool_records,
            llm_provider_used=self.llm_provider.provider,
            llm_model_used=self.llm_provider.model,
        )
