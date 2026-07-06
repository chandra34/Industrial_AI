from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="ok")
    app_name: str
    milvus_collection: str
    llm_model: str
