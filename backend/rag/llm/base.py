from abc import ABC, abstractmethod
from backend.config.settings import Settings


class LLMProvider(ABC):
    """Abstract base class for all LLM service providers."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abstractmethod
    async def generate_answer(self, messages: list[dict[str, str]]) -> str:
        """Send messages to the LLM and return the assistant reply text."""
        pass

    async def generate_structured_output(
        self,
        messages: list[dict[str, str]],
        response_model: type,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> str:
        """Send messages to the LLM and enforce a strict JSON output matching ``response_model``."""
        raise NotImplementedError("Structured output is not implemented for this LLM provider.")
