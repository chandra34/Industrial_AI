import logging
from google import genai
from google.genai import types, errors

from backend.config.settings import Settings
from backend.rag.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class GeminiLLMService(LLMProvider):
    """Generate answers via the Google Gemini API using the google-genai SDK."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        if not settings.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is required when using the gemini provider. "
                "Set it in .env or the environment."
            )
        self.client = genai.Client(api_key=settings.gemini_api_key)
        logger.info("Using Gemini LLM model %s", settings.llm_model)

    async def generate_answer(self, messages: list[dict[str, str]]) -> str:
        """Send messages to the LLM and return the assistant reply text."""
        try:
            logger.info("Generating answer using Gemini provider with model: %s", self.settings.llm_model)
            system_instruction = None
            contents = []

            for msg in messages:
                role = msg.get("role")
                content = msg.get("content", "")
                if role == "system":
                    system_instruction = content
                else:
                    # google-genai expects 'user' or 'model' roles
                    gemini_role = "user" if role == "user" else "model"
                    contents.append(
                        types.Content(
                            role=gemini_role,
                            parts=[types.Part.from_text(text=content)]
                        )
                    )

            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=self.settings.llm_temperature,
                max_output_tokens=self.settings.llm_max_tokens,
            )

            response = await self.client.aio.models.generate_content(
                model=self.settings.llm_model,
                contents=contents,
                config=config,
            )

            content = response.text
            if not content:
                raise RuntimeError("Gemini returned an empty response")
            return content.strip()

        except errors.APIError as exc:
            logger.error("Gemini API error: %s", exc)
            raise RuntimeError(f"Gemini LLM service returned an API error: {exc.message}") from exc
        except Exception as exc:
            logger.exception("LLM generation failed due to unexpected error")
            raise RuntimeError("An unexpected error occurred during answer generation.") from exc
