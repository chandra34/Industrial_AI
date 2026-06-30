from dataclasses import dataclass

from backend.config.settings import Settings
from backend.rag.llm import LLMService
from backend.rag.prompts import build_messages
from backend.rag.retrieval import RetrievedChunk, RetrievalService


@dataclass(slots=True)
class QAResult:
    answer: str
    sources: list[RetrievedChunk]


class RAGPipeline:
    """Orchestrate retrieval, prompt assembly, and LLM answer generation."""

    def __init__(
        self,
        settings: Settings,
        retrieval_service: RetrievalService,
        llm_service: LLMService,
    ) -> None:
        self.settings = settings
        self.retrieval_service = retrieval_service
        self.llm_service = llm_service

    async def answer_question(self, question: str, user_id: str, top_k: int | None = None) -> QAResult:
        """Retrieve relevant chunks and generate an answer for ``question``."""
        sources = await self.retrieval_service.search(question, user_id=user_id, top_k=top_k)
        messages = build_messages(question, sources, max_chars=self.settings.max_context_chars)
        answer = await self.llm_service.generate_answer(messages)
        return QAResult(answer=answer, sources=sources)

