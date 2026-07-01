import logging
import time
from dataclasses import dataclass

from backend.config.settings import Settings
from backend.rag.llm import LLMProvider
from backend.rag.prompts import build_messages
from backend.rag.retrieval import RetrievedChunk, RetrievalService

logger = logging.getLogger(__name__)


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
        llm_service: LLMProvider,
    ) -> None:
        self.settings = settings
        self.retrieval_service = retrieval_service
        self.llm_service = llm_service

    async def answer_question(self, question: str, user_id: str, top_k: int | None = None) -> QAResult:
        """Retrieve relevant chunks and generate an answer for ``question``."""
        question_preview = (question[:60] + "...") if len(question) > 60 else question
        logger.info("Query flow: query received | question_preview: '%s' | user_id: %s", question_preview, user_id)
        
        sources = await self.retrieval_service.search(question, user_id=user_id, top_k=top_k)
        
        # Build prompt messages
        messages = build_messages(question, sources, max_chars=self.settings.max_context_chars)
        
        # LLM inference
        start_llm = time.perf_counter()
        answer = await self.llm_service.generate_answer(messages)
        duration_llm = time.perf_counter() - start_llm
        logger.info("Query flow: answer generated | duration: %.3fs", duration_llm)
        
        logger.info("Query flow: request completed successfully")
        return QAResult(answer=answer, sources=sources)


