from backend.config.settings import Settings
from backend.rag.llm.base import LLMProvider
from backend.rag.llm.groq_service import GroqLLMService
from backend.rag.llm.openai_service import OpenAILLMService
from backend.rag.llm.gemini_service import GeminiLLMService
from backend.rag.llm.anthropic_service import AnthropicLLMService


class LLMFactory:
    """Create an LLM provider from application settings."""

    @staticmethod
    def create(settings: Settings) -> LLMProvider:
        """Instantiate the configured LLM provider."""
        provider = settings.llm_provider.lower().strip()

        if provider == "groq":
            return GroqLLMService(settings)
        elif provider == "openai":
            return OpenAILLMService(settings)
        elif provider == "gemini":
            return GeminiLLMService(settings)
        elif provider == "anthropic":
            return AnthropicLLMService(settings)

        raise ValueError(f"Unknown LLM provider: {provider}")
