import logging
import openai
from openai import AsyncOpenAI

from backend.config.settings import Settings
from backend.rag.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class OpenAILLMService(LLMProvider):
    """Generate answers via the OpenAI chat completions API."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        if not settings.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is required when using the openai provider. "
                "Set it in .env or the environment."
            )
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=20.0)
        logger.info("Using OpenAI LLM model %s", settings.llm_model)

    async def generate_answer(self, messages: list[dict[str, str]]) -> str:
        """Send messages to the LLM and return the assistant reply text."""
        try:
            logger.info("Generating answer using OpenAI provider with model: %s", self.settings.llm_model)
            completion = await self.client.chat.completions.create(
                model=self.settings.llm_model,
                messages=messages,
                temperature=self.settings.llm_temperature,
                max_tokens=self.settings.llm_max_tokens,
            )
            content = completion.choices[0].message.content
            if not content:
                raise RuntimeError("OpenAI returned an empty response")
            return content.strip()
        except openai.APITimeoutError as exc:
            logger.warning("OpenAI API request timed out: %s", exc)
            raise RuntimeError("The LLM request timed out. Please try again.") from exc
        except openai.RateLimitError as exc:
            logger.warning("OpenAI API rate limit hit: %s", exc)
            raise RuntimeError("The LLM service is currently rate-limited. Please wait a moment and try again.") from exc
        except openai.APIConnectionError as exc:
            logger.warning("OpenAI API connection failure: %s", exc)
            raise RuntimeError("Could not connect to the LLM service. Please check your network and try again.") from exc
        except openai.APIStatusError as exc:
            logger.error("OpenAI API returned status code %d: %s", exc.status_code, exc.message)
            raise RuntimeError(f"LLM service returned an error status ({exc.status_code}).") from exc
        except Exception as exc:
            logger.exception("LLM generation failed due to unexpected error")
            raise RuntimeError("An unexpected error occurred during answer generation.") from exc
