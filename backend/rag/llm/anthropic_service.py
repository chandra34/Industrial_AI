import logging
import anthropic
from anthropic import AsyncAnthropic

from backend.config.settings import Settings
from backend.rag.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class AnthropicLLMService(LLMProvider):
    """Generate answers via the Anthropic Claude API using the anthropic SDK."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        if not settings.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is required when using the anthropic provider. "
                "Set it in .env or the environment."
            )
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=20.0)
        logger.info("Using Anthropic LLM model %s", settings.llm_model)

    async def generate_answer(self, messages: list[dict[str, str]]) -> str:
        """Send messages to the LLM and return the assistant reply text."""
        try:
            logger.info("Generating answer using Anthropic provider with model: %s", self.settings.llm_model)
            
            system_prompt = ""
            filtered_messages = []

            for msg in messages:
                role = msg.get("role")
                content = msg.get("content", "")
                if role == "system":
                    system_prompt = content
                else:
                    # Anthropic API requires messages to strictly alternate 'user' and 'assistant' roles
                    anthropic_role = "assistant" if role in ("assistant", "model") else "user"
                    filtered_messages.append({
                        "role": anthropic_role,
                        "content": content
                    })

            completion = await self.client.messages.create(
                model=self.settings.llm_model,
                messages=filtered_messages,
                system=system_prompt if system_prompt else None,
                temperature=self.settings.llm_temperature,
                max_tokens=self.settings.llm_max_tokens,
            )

            # In the Messages API, content is returned as a list of ContentBlocks
            if not completion.content or not completion.content[0].text:
                raise RuntimeError("Anthropic returned an empty response")
            return completion.content[0].text.strip()

        except anthropic.APITimeoutError as exc:
            logger.warning("Anthropic API request timed out: %s", exc)
            raise RuntimeError("The LLM request timed out. Please try again.") from exc
        except anthropic.RateLimitError as exc:
            logger.warning("Anthropic API rate limit hit: %s", exc)
            raise RuntimeError("The LLM service is currently rate-limited. Please wait a moment and try again.") from exc
        except anthropic.APIConnectionError as exc:
            logger.warning("Anthropic API connection failure: %s", exc)
            raise RuntimeError("Could not connect to the LLM service. Please check your network and try again.") from exc
        except anthropic.APIStatusError as exc:
            logger.error("Anthropic API returned status code %d: %s", exc.status_code, exc.message)
            raise RuntimeError(f"LLM service returned an error status ({exc.status_code}).") from exc
        except Exception as exc:
            logger.exception("LLM generation failed due to unexpected error")
            raise RuntimeError("An unexpected error occurred during answer generation.") from exc
