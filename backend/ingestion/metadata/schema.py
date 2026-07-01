from pydantic import BaseModel, Field

class ChunkMetadata(BaseModel):
    """Metadata schema matching step 2 requirements."""
    page: int = Field(..., description="1-indexed page number of the source chunk")
    section: str = Field(default="", description="Hierarchy of sections / headings")
    source: str = Field(..., description="Original filename of the parsed document")
