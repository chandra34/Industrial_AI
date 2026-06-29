import logging

from groq import AsyncGroq, APITimeoutError, RateLimitError, APIStatusError

from backend.config.settings import Settings

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        if not settings.groq_api_key:
            raise ValueError(
                "GROQ_API_KEY is required. Set it in .env or the environment."
            )
        self.client = AsyncGroq(api_key=settings.groq_api_key, timeout=20.0)
        logger.info("Using Groq LLM model %s", settings.llm_model)

    async def generate_answer(self, messages: list[dict[str, str]]) -> str:
        try:
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

