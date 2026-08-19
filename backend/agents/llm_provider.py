"""
Universal LLM Provider Adapter supporting OpenAI, Gemini, and Anthropic.
"""

import os
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class UnifiedToolCall(BaseModel):
    """Normalized tool call representation across OpenAI, Gemini, and Anthropic providers."""

    id: str
    name: str
    arguments: Dict[str, Any]


class UnifiedMessage(BaseModel):
    """Normalized message structure across providers."""

    role: str
    content: Optional[str] = None
    tool_calls: Optional[List[UnifiedToolCall]] = None


class LLMProvider:
    """Universal adapter supporting OpenAI, Gemini, and Anthropic clients."""

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """Initialize LLM Provider.

        :param provider: 'openai', 'gemini', or 'anthropic'. If None, reads LLM_PROVIDER from environment.
        :param model: Model name. If None, reads LLM_MODEL from environment.
        """
        self.provider = (provider or os.getenv("LLM_PROVIDER", "openai")).lower()
        if self.provider == "gemini":
            self.model = model or os.getenv("LLM_MODEL", "gemini-2.5-flash")
        elif self.provider == "anthropic":
            self.model = model or os.getenv("LLM_MODEL", "claude-3-5-sonnet-20241022")
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
        elif self.provider == "anthropic":
            return await self._generate_anthropic(messages, tools)
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

    async def _generate_anthropic(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> Tuple[UnifiedMessage, Any]:
        """Execute tool calling step via Anthropic AsyncAnthropic client."""
        from anthropic import AsyncAnthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for the anthropic agent provider.")
        client = AsyncAnthropic(api_key=api_key, timeout=30.0)

        # --- 1. Convert OpenAI tool schemas to Anthropic format ---
        anthropic_tools = []
        for t in tools:
            if isinstance(t, dict) and t.get("type") == "function":
                fn = t.get("function", {})
                anthropic_tools.append({
                    "name": fn.get("name"),
                    "description": fn.get("description"),
                    "input_schema": fn.get("parameters"),
                })

        # --- 2. Convert message history to Anthropic format ---
        system_instruction = None
        anthropic_messages: List[Dict[str, Any]] = []

        for m in messages:
            role = m.get("role")
            content = m.get("content")

            if role == "system":
                system_instruction = content
                continue

            # Pass through Anthropic-native assistant turns (contains ContentBlock lists)
            if role == "assistant" and isinstance(content, list):
                anthropic_messages.append({"role": "assistant", "content": content})
                continue

            if role == "user":
                anthropic_messages.append({"role": "user", "content": str(content or "")})

            elif role == "assistant":
                anthropic_messages.append({
                    "role": "assistant",
                    "content": str(content or ""),
                })

            elif role == "tool":
                # Anthropic requires tool results as content blocks inside a "user" turn.
                # Merge consecutive tool results into one user message.
                tool_result_block = {
                    "type": "tool_result",
                    "tool_use_id": m.get("tool_call_id", "unknown"),
                    "content": str(content or ""),
                }
                if (
                    anthropic_messages
                    and anthropic_messages[-1].get("role") == "user"
                    and isinstance(anthropic_messages[-1].get("content"), list)
                    and anthropic_messages[-1]["content"]
                    and isinstance(anthropic_messages[-1]["content"][0], dict)
                    and anthropic_messages[-1]["content"][0].get("type") == "tool_result"
                ):
                    # Merge into existing user turn containing tool_result blocks
                    anthropic_messages[-1]["content"].append(tool_result_block)
                else:
                    anthropic_messages.append({
                        "role": "user",
                        "content": [tool_result_block],
                    })

        # --- 3. Call Anthropic Messages API ---
        create_kwargs: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": 2048,
            "messages": anthropic_messages,
            "temperature": 0.1,
        }
        if system_instruction:
            create_kwargs["system"] = system_instruction
        if anthropic_tools:
            create_kwargs["tools"] = anthropic_tools

        try:
            response = await client.messages.create(**create_kwargs)
        except Exception as exc:
            logger.error("Anthropic API call failed during agent step: %s", exc)
            raise RuntimeError(f"Anthropic LLM service error: {exc}") from exc

        # --- 4. Parse response content blocks into UnifiedMessage ---
        tool_calls_data = None
        text_content = None

        for block in response.content:
            if block.type == "text":
                text_content = block.text
            elif block.type == "tool_use":
                if not tool_calls_data:
                    tool_calls_data = []
                tool_calls_data.append(
                    UnifiedToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input if isinstance(block.input, dict) else {},
                    )
                )

        unified = UnifiedMessage(
            role="assistant",
            content=text_content,
            tool_calls=tool_calls_data,
        )
        return unified, response

    async def _generate_gemini(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> Tuple[UnifiedMessage, Any]:
        """Execute tool calling step via Google GenAI Client with full context history using raw REST payloads."""
        from google.genai import Client

        api_key = os.getenv("GEMINI_API_KEY")
        client = Client(api_key=api_key) if api_key else Client()

        contents: List[Dict[str, Any]] = []
        system_instruction = None

        for m in messages:
            # If the history item is already a raw REST dictionary (containing role and parts), pass it directly
            if isinstance(m, dict) and "role" in m and "parts" in m:
                contents.append(m)
                continue

            role = m.get("role")
            content = m.get("content", "")

            if role == "system":
                system_instruction = content

            elif role == "user":
                contents.append({
                    "role": "user",
                    "parts": [{"text": str(content or "")}]
                })

            elif role == "assistant":
                parts = []
                if content:
                    parts.append({"text": str(content)})

                # Map history of assistant's tool call requests
                if m.get("tool_calls"):
                    for tc in m["tool_calls"]:
                        tc_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                        tc_args = tc.get("arguments") if isinstance(tc, dict) else getattr(tc, "arguments", {})
                        if tc_name:
                            parts.append({
                                "functionCall": {
                                    "name": tc_name,
                                    "args": tc_args or {}
                                }
                            })
                contents.append({"role": "model", "parts": parts if parts else [{"text": ""}]})

            elif role == "tool":
                # Map history of tool response results back to the model
                tool_name = m.get("name", "unknown_tool")
                try:
                    resp_dict = json.loads(content) if isinstance(content, str) else content
                except Exception:
                    resp_dict = {"result": content}

                if not isinstance(resp_dict, dict):
                    resp_dict = {"result": resp_dict}

                fn_response_part = {
                    "functionResponse": {
                        "name": tool_name,
                        "response": resp_dict
                    }
                }

                # Gemini requires ALL functionResponse parts from a single model
                # turn to be grouped into ONE user message. Merge consecutive tool
                # responses into the same user entry to avoid invalid consecutive
                # user turns (HTTP 400).
                if (
                    contents
                    and contents[-1].get("role") == "user"
                    and contents[-1].get("parts")
                    and "functionResponse" in contents[-1]["parts"][-1]
                ):
                    contents[-1]["parts"].append(fn_response_part)
                else:
                    contents.append({
                        "role": "user",
                        "parts": [fn_response_part]
                    })

        request_dict = {
            "contents": contents,
        }

        if tools:
            func_declarations = []
            for t in tools:
                if isinstance(t, dict) and t.get("type") == "function":
                    fn = t.get("function", {})
                    func_declarations.append({
                        "name": fn.get("name"),
                        "description": fn.get("description"),
                        "parameters": fn.get("parameters"),
                    })
            if func_declarations:
                request_dict["tools"] = [{"functionDeclarations": func_declarations}]

        # Set configuration options
        request_dict["generation_config"] = {"temperature": 0.1}
        if system_instruction:
            request_dict["system_instruction"] = {
                "parts": [{"text": system_instruction}]
            }

        # Run direct REST generateContent request to preserve thoughtSignature metadata
        path = f"models/{self.model}:generateContent"
        response_dict = await client._api_client.async_request("POST", path, request_dict)

        tool_calls_data = None
        text_content = None

        candidates = response_dict.get("candidates", [])
        if candidates:
            candidate = candidates[0]
            content_obj = candidate.get("content", {})
            parts = content_obj.get("parts", [])
            if parts:
                for part in parts:
                    if "text" in part:
                        text_content = part["text"]
                    elif "functionCall" in part:
                        call = part["functionCall"]
                        if not tool_calls_data:
                            tool_calls_data = []
                        tool_calls_data.append(
                            UnifiedToolCall(
                                id=call.get("id", "call_0"),
                                name=call.get("name"),
                                arguments=call.get("args") or {},
                            )
                        )

        unified = UnifiedMessage(
            role="assistant",
            content=text_content,
            tool_calls=tool_calls_data,
        )
        return unified, response_dict
