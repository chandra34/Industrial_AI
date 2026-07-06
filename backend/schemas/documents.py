from pydantic import BaseModel, Field


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
