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
        
        # Log correlation complete
        logger.info("Query flow: request completed successfully")
        return QAResult(answer=answer, sources=sources)

    async def review_permit(self, request: "PTWReviewRequest", user_id: str) -> "SafetyReviewReport":
        """Audit a Permit-to-Work request against retrieved safety standards and return a structured report."""
        from groq import Groq
        from fastapi.concurrency import run_in_threadpool
        from backend.schemas.schemas import SafetyReviewReport, PTWReviewRequest
        from backend.rag.prompts import build_safety_review_messages
        
        logger.info(
            "Query flow: starting permit safety review | user_id: %s | equipment: %s | manufacturer: %s",
            user_id, request.equipment, request.manufacturer
        )

        # Build custom metadata filter expression if overrides are provided
        filters = []
        if request.manufacturer and request.manufacturer.strip().lower() != "unknown":
            filters.append(f'manufacturer == "{request.manufacturer.strip().lower()}"')
        if request.equipment and request.equipment.strip().lower() != "unknown":
            filters.append(f'equipment == "{request.equipment.strip().lower()}"')
        
        metadata_filter = " and ".join(filters) if filters else None

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

        # 3. Call Groq with structured outputs
        if not self.settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is not configured")

        client = Groq(api_key=self.settings.groq_api_key)

        def call_groq():
            return client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=messages,
                temperature=0.0,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "SafetyReviewReport",
                        "strict": True,
                        "schema": SafetyReviewReport.model_json_schema()
                    }
                }
            )

        start_llm = time.perf_counter()
        completion = await run_in_threadpool(call_groq)
        content = completion.choices[0].message.content.strip()
        duration_llm = time.perf_counter() - start_llm
        logger.info("Query flow: safety review report generated | duration: %.3fs", duration_llm)

        # Parse the structured response into the Pydantic response model
        return SafetyReviewReport.model_validate_json(content)


