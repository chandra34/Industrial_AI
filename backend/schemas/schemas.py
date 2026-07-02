"""Pydantic request and response models for the API."""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="ok")
    app_name: str
    milvus_collection: str
    llm_model: str


class UploadResponse(BaseModel):
    status: str = Field(default="success")
    document_id: str
    filename: str
    stored_path: str
    page_count: int
    chunk_count: int
    embedded_count: int


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


class QueryResponse(BaseModel):
    status: str = Field(default="success")
    question: str
    answer: str
    source_chunks: list[SourceChunkResponse]
    retrieved_chunk_count: int


class DocumentItem(BaseModel):
    document_id: str
    filename: str
    page_count: int
    chunk_count: int


class DocumentListResponse(BaseModel):
    status: str = Field(default="success")
    documents: list[DocumentItem]


class DeleteResponse(BaseModel):
    status: str = Field(default="success")
    message: str


class UploadJobAcceptedResponse(BaseModel):
    status: str = Field(default="accepted")
    job_id: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str  # pending, processing, completed, failed
    message: str | None = None
    result: UploadResponse | None = None
    error: str | None = None
