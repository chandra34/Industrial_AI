import json
import numpy as np
from backend.config.settings import Settings
from backend.rag.embeddings.base import EmbeddingProvider
from backend.rag.llm.base import LLMProvider

class MockEmbeddingProvider(EmbeddingProvider):
    """Mock Embedding Provider returning zero vectors."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)

    async def _embed_batch(self, texts: list[str]) -> np.ndarray:
        return np.zeros((len(texts), self.settings.milvus_dimension), dtype=np.float32)


class MockLLMProvider(LLMProvider):
    """Mock LLM Provider returning predefined text or structured JSON."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.calls = []
        self.answer_response = "Mock Answer"
        self.structured_response = None

    async def generate_answer(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(("generate_answer", messages))
        return self.answer_response

    async def generate_structured_output(
        self,
        messages: list[dict[str, str]],
        response_model: type,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> str:
        self.calls.append(("generate_structured_output", messages, response_model, model, temperature))
        
        if self.structured_response is not None:
            if isinstance(self.structured_response, str):
                return self.structured_response
            return json.dumps(self.structured_response)

        # Generate default valid JSON mock schemas depending on response_model
        name = response_model.__name__
        if "SafetyReviewReport" in name:
            return json.dumps({
                "status": "Safe",
                "summary": "No industrial safety gaps found.",
                "findings": []
            })
        elif "QueryIntent" in name:
            return json.dumps({
                "manufacturer": "unknown",
                "equipment": "unknown"
            })
        elif "DocumentMetadata" in name:
            return json.dumps({
                "document_type": "Unknown",
                "manufacturer": "unknown",
                "equipment": "unknown",
                "revision": "Unknown",
                "language": "English"
            })
            
        return "{}"


class MockMilvusStore:
    """Mock Milvus Store bypassing PyMilvus DB connections."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings
        self.collection_name = settings.milvus_collection_name if settings else "test_collection"
        self.inserted_chunks = []
        self.deleted_documents = []
        self.search_results = []
        self.check_health_status = True

    async def insert_chunks(self, chunks: list, embeddings: np.ndarray, user_id: str) -> int:
        self.inserted_chunks.append((chunks, embeddings, user_id))
        return len(chunks)

    async def search(
        self,
        query_embedding: np.ndarray,
        top_k: int,
        user_id: str,
        metadata_filter: str | None = None,
    ) -> list:
        return self.search_results

    async def hybrid_search(
        self,
        query_embedding: np.ndarray,
        query_text: str,
        top_k: int,
        user_id: str,
        metadata_filter: str | None = None,
    ) -> list:
        return self.search_results

    async def delete_document(self, document_id: str, user_id: str) -> None:
        self.deleted_documents.append((document_id, user_id))

    async def close(self) -> None:
        pass

    def check_health(self) -> bool:
        return self.check_health_status
