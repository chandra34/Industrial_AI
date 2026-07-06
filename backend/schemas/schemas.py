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
    document_type: str | None = None
    manufacturer: str | None = None
    equipment: str | None = None
    revision: str | None = None
    language: str | None = None


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
    revision: str | None = None
    language: str | None = None
    paragraph: str | None = None


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
    document_type: str | None = None
    manufacturer: str | None = None
    equipment: str | None = None
    revision: str | None = None
    language: str | None = None


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


class SafetyFinding(BaseModel):
    model_config = {"extra": "forbid"}

    severity: str = Field(description="Severity of the finding: 'Low', 'Medium', 'High', or 'Critical'")
    finding_type: str = Field(description="Type of safety gap: 'Missing Lockout/Isolation', 'Incorrect PPE', 'Procedural Deviation', 'Hazard Warning', or 'Other'")
    description: str = Field(description="Detailed explanation of the safety finding or gap")
    recommendation: str = Field(description="Actionable corrective recommendation to mitigate the risk")
    reference_source: str = Field(description="Source document or SOP reference, or empty string if not applicable")


class SafetyReviewReport(BaseModel):
    model_config = {"extra": "forbid"}

    status: str = Field(description="Overall audit outcome: 'Safe', 'Needs Review', or 'Unsafe'")
    summary: str = Field(description="High-level executive summary of the safety audit findings")
    findings: list[SafetyFinding] = Field(description="List of specific safety findings and procedural gaps identified")


class PTWReviewRequest(BaseModel):
    permit_text: str = Field(min_length=10, description="The raw permit text or steps of the task to be reviewed")
    equipment: str | None = Field(default=None, description="Optional equipment name/model to filter the source manuals")
    manufacturer: str | None = Field(default=None, description="Optional manufacturer to filter the source manuals")
