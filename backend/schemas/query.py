from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, description="User question to answer")
    top_k: int | None = Field(default=None, ge=1, le=20, description="Optional retrieval depth")


class SourceChunkResponse(BaseModel):
    document_id: str
    source_filename: str
    page_number: int
    chunk_index: int
    score: float
    chunk_text: str
    document_type: str | None = None
    manufacturer: str | None = None
    equipment: str | None = None
    section: str | None = None


class QueryResponse(BaseModel):
    status: str = Field(default="success")
    question: str
    answer: str
    source_chunks: list[SourceChunkResponse]
    retrieved_chunk_count: int
