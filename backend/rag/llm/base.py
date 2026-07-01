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
