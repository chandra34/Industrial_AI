import logging
from groq import AsyncGroq, APITimeoutError, RateLimitError, APIStatusError

from backend.config.settings import Settings
from backend.rag.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class GroqLLMService(LLMProvider):
    """Generate answers via the Groq chat completions API."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        if not settings.groq_api_key:
            raise ValueError(
                "GROQ_API_KEY is required. Set it in .env or the environment."
            )
        self.client = AsyncGroq(api_key=settings.groq_api_key, timeout=20.0)
        logger.info("Using Groq LLM model %s", settings.llm_model)

    async def generate_answer(self, messages: list[dict[str, str]]) -> str:
        """Send messages to the LLM and return the assistant reply text."""
        try:
            logger.info("Generating answer using Groq provider with model: %s", self.settings.llm_model)
            completion = await self.client.chat.completions.create(
                model=self.settings.llm_model,
                messages=messages,
                temperature=self.settings.llm_temperature,
                max_tokens=self.settings.llm_max_tokens,
            )
            content = completion.choices[0].message.content
            if not content:
                raise RuntimeError("Groq returned an empty response")
            return content.strip()
        except APITimeoutError as exc:
            logger.warning("Groq API request timed out: %s", exc)
            raise RuntimeError("The LLM request timed out. Please try again.") from exc
        except RateLimitError as exc:
            logger.warning("Groq API rate limit hit: %s", exc)
            raise RuntimeError("The LLM service is currently rate-limited. Please wait a moment and try again.") from exc
        except APIStatusError as exc:
            logger.error("Groq API returned status code %d: %s", exc.status_code, exc.message)
            raise RuntimeError(f"LLM service returned an error status ({exc.status_code}).") from exc
        except Exception as exc:
            logger.exception("LLM generation failed due to unexpected error")
            raise RuntimeError("An unexpected error occurred during answer generation.") from exc

    async def generate_structured_output(
        self,
        messages: list[dict[str, str]],
        response_model: type,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> str:
        """Send messages to the LLM and enforce a strict JSON output matching ``response_model``."""
        try:
            logger.info("Generating structured output using Groq provider with model: %s", model or self.settings.llm_model)
            completion = await self.client.chat.completions.create(
                model=model or self.settings.llm_model,
                messages=messages,
                temperature=temperature,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": response_model.__name__,
                        "strict": True,
                        "schema": response_model.model_json_schema()
                    }
                }
            )
            content = completion.choices[0].message.content
            if not content:
                raise RuntimeError("Groq returned an empty response")
            return content.strip()
        except APITimeoutError as exc:
            logger.warning("Groq API request timed out: %s", exc)
            raise RuntimeError("The LLM request timed out. Please try again.") from exc
        except RateLimitError as exc:
            logger.warning("Groq API rate limit hit: %s", exc)
            raise RuntimeError("The LLM service is currently rate-limited. Please wait a moment and try again.") from exc
        except APIStatusError as exc:
            logger.error("Groq API returned status code %d: %s", exc.status_code, exc.message)
            raise RuntimeError(f"LLM service returned an error status ({exc.status_code}).") from exc
        except Exception as exc:
            logger.exception("LLM structured output generation failed due to unexpected error")
            raise RuntimeError("An unexpected error occurred during structured answer generation.") from exc
