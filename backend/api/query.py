import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.schemas.schemas import QueryRequest, QueryResponse, SourceChunkResponse
from backend.api.auth import get_current_user, FirebaseUser
from backend.api.dependencies import get_rag_pipeline
from backend.rag.pipeline import RAGPipeline

logger = logging.getLogger(__name__)
router = APIRouter()


def _clean_filename(filename: str, doc_id: str) -> str:
    if filename and filename.startswith(f"{doc_id}_"):
        return filename[len(doc_id) + 1 :]
    return filename or "Unknown"


@router.post("/query", response_model=QueryResponse)
async def query_documents(
    payload: QueryRequest,
    current_user: FirebaseUser = Depends(get_current_user),
    pipeline: RAGPipeline = Depends(get_rag_pipeline),
) -> QueryResponse:
    """Run RAG retrieval and generation for a user question."""

    try:
        result = await pipeline.answer_question(payload.question, user_id=current_user.uid, top_k=payload.top_k)
    except Exception as exc:
        logger.exception("Query failed")
        raise HTTPException(status_code=500, detail="An internal server error occurred while processing your query.") from exc

    return QueryResponse(
        question=payload.question,
        answer=result.answer,
        source_chunks=[
            SourceChunkResponse(
                document_id=chunk.document_id,
                source_filename=_clean_filename(chunk.source_filename, chunk.document_id),
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                score=chunk.score,
                chunk_text=chunk.chunk_text,
            )
            for chunk in result.sources
        ],
        retrieved_chunk_count=len(result.sources),
    )
