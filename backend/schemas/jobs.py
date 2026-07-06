from pydantic import BaseModel, Field
from backend.schemas.documents import UploadResponse


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
