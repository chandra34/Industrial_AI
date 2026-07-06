import logging
import time
from dataclasses import dataclass

from backend.config.settings import Settings
from backend.rag.llm import LLMProvider
from backend.rag.prompts import build_messages
from backend.rag.retrieval import RetrievedChunk, RetrievalService
from backend.vectordb import build_scalar_filter

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
        
        # Log correlation complete
        logger.info("Query flow: request completed successfully")
        return QAResult(answer=answer, sources=sources)

    async def review_permit(self, request: "PTWReviewRequest", user_id: str) -> "SafetyReviewReport":
        """Audit a Permit-to-Work request against retrieved safety standards and return a structured report."""
        from backend.schemas.safety import SafetyReviewReport, PTWReviewRequest
        from backend.rag.prompts import build_safety_review_messages
        
        logger.info(
            "Query flow: starting permit safety review | user_id: %s | equipment: %s | manufacturer: %s",
            user_id, request.equipment, request.manufacturer
        )

        # Build custom metadata filter expression if overrides are provided
        metadata_filter = build_scalar_filter(request.manufacturer, request.equipment)

        # 1. Retrieve relevant safety standards context (using permit text as search query)
        sources = await self.retrieval_service.search(
            query=request.permit_text,
            user_id=user_id,
            metadata_filter=metadata_filter
        )

        # 2. Build prompt messages
        messages = build_safety_review_messages(
            permit_text=request.permit_text,
            chunks=sources,
            max_chars=self.settings.max_context_chars
        )

        # 3. Call structured output on LLM Service
        start_llm = time.perf_counter()
        content = await self.llm_service.generate_structured_output(
            messages=messages,
            response_model=SafetyReviewReport,
            model="openai/gpt-oss-120b",
            temperature=0.0
        )
        duration_llm = time.perf_counter() - start_llm
        logger.info("Query flow: safety review report generated | duration: %.3fs", duration_llm)

        # Parse the structured response into the Pydantic response model
        return SafetyReviewReport.model_validate_json(content)


