"""
Universal LLM Provider Adapter supporting OpenAI and Gemini.
"""

import os
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class UnifiedToolCall(BaseModel):
    """Normalized tool call representation across OpenAI and Gemini providers."""

    id: str
    name: str
    arguments: Dict[str, Any]


class UnifiedMessage(BaseModel):
    """Normalized message structure across providers."""

    role: str
    content: Optional[str] = None
    tool_calls: Optional[List[UnifiedToolCall]] = None


class LLMProvider:
    """Universal adapter supporting both OpenAI and Gemini clients."""

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """Initialize LLM Provider.

        :param provider: 'openai' or 'gemini'. If None, reads LLM_PROVIDER from environment.
        :param model: Model name. If None, reads LLM_MODEL from environment.
        """
        self.provider = (provider or os.getenv("LLM_PROVIDER", "openai")).lower()
        if self.provider == "gemini":
            self.model = model or os.getenv("LLM_MODEL", "gemini-2.5-flash")
        else:
            self.model = model or os.getenv("LLM_MODEL", "gpt-4o")

        logger.info("Initialized LLMProvider(provider='%s', model='%s')", self.provider, self.model)

    async def generate_step(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> Tuple[UnifiedMessage, Any]:
        """Execute a single generation step and normalize tool calls.

        :param messages: List of conversation message dictionaries.
        :param tools: OpenAI-style tool definition list.
        :return: Tuple of (UnifiedMessage, raw_response_object)
        """
        if self.provider == "gemini":
            return await self._generate_gemini(messages, tools)
        else:
            return await self._generate_openai(messages, tools)

    async def _generate_openai(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> Tuple[UnifiedMessage, Any]:
        """Execute tool calling step via OpenAI AsyncOpenAI client."""
        from openai import AsyncOpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        client = AsyncOpenAI(api_key=api_key) if api_key else AsyncOpenAI()

        response = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            temperature=0.1,
        )
        msg = response.choices[0].message
        tool_calls_data = None
        if msg.tool_calls:
            tool_calls_data = [
                UnifiedToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments,
                )
                for tc in msg.tool_calls
            ]

        unified = UnifiedMessage(
            role="assistant",
            content=msg.content,
            tool_calls=tool_calls_data,
        )
        return unified, msg

    async def _generate_gemini(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> Tuple[UnifiedMessage, Any]:
        """Execute tool calling step via Google GenAI Client with full context history."""
        from google.genai import Client, types

        api_key = os.getenv("GEMINI_API_KEY")
        client = Client(api_key=api_key) if api_key else Client()

        contents: List[types.Content] = []
        system_instruction = None

        for m in messages:
            role = m.get("role")
            content = m.get("content", "")

            if role == "system":
                system_instruction = content

            elif role == "user":
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=str(content or ""))]
                    )
                )

            elif role == "assistant":
                parts = []
                if content:
                    parts.append(types.Part.from_text(text=str(content)))

                # Map history of assistant's tool call requests
                if m.get("tool_calls"):
                    for tc in m["tool_calls"]:
                        tc_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                        tc_args = tc.get("arguments") if isinstance(tc, dict) else getattr(tc, "arguments", {})
                        if tc_name:
                            parts.append(
                                types.Part.from_function_call(
                                    name=tc_name,
                                    args=tc_args or {}
                                )
                            )
                contents.append(types.Content(role="model", parts=parts if parts else [types.Part.from_text(text="")]))

            elif role == "tool":
                # Map history of tool response results back to the model
                tool_name = m.get("name", "unknown_tool")
                try:
                    resp_dict = json.loads(content) if isinstance(content, str) else content
                except Exception:
                    resp_dict = {"result": content}

                if not isinstance(resp_dict, dict):
                    resp_dict = {"result": resp_dict}

                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_function_response(
                                name=tool_name,
                                response=resp_dict
                            )
                        ]
                    )
                )

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.1,
            tools=tools if tools else None,
        )

        response = await client.aio.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
        )

        tool_calls_data = None
        if hasattr(response, "function_calls") and response.function_calls:
            tool_calls_data = [
                UnifiedToolCall(
                    id=f"call_{idx}",
                    name=call.name,
                    arguments=dict(call.args) if hasattr(call, "args") and call.args else {},
                )
                for idx, call in enumerate(response.function_calls)
            ]

        text_content = None
        try:
            text_content = response.text
        except ValueError:
            text_content = None

        unified = UnifiedMessage(
            role="assistant",
            content=text_content,
            tool_calls=tool_calls_data,
        )
        return unified, response
