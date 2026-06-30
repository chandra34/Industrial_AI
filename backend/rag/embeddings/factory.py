from backend.config.settings import Settings
from backend.rag.embeddings.base import EmbeddingProvider
from backend.rag.embeddings.gemini import GeminiEmbedding
from backend.rag.embeddings.openai_emb import OpenAIEmbedding
from backend.rag.embeddings.voyage_emb import VoyageEmbedding

class EmbeddingFactory:
    """Create an embedding provider from application settings."""

    @staticmethod
    def create(settings: Settings) -> EmbeddingProvider:
        """Instantiate the configured embedding provider."""
        provider = settings.embedding_provider.lower().strip()
        
        if provider == "gemini":
            return GeminiEmbedding(settings)
        elif provider == "openai":
            return OpenAIEmbedding(settings)
        elif provider == "voyage":
            return VoyageEmbedding(settings)
            
        raise ValueError(f"Unknown embedding provider: {provider}")
