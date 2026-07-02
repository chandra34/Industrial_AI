"""SQLAlchemy ORM models for document metadata and ingestion job tracking."""

from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Document(Base):
    """Tracks uploaded document metadata and ownership."""

    __tablename__ = "documents"

    id = Column(String, primary_key=True, doc="UUID hex string matching the document_id used in Milvus")
    user_id = Column(String, nullable=False, index=True)
    filename = Column(String, nullable=False, doc="Original user-facing filename without the document_id prefix")
    stored_path = Column(String, nullable=False, doc="Absolute or relative path to the raw PDF on disk")
    page_count = Column(Integer, nullable=False, default=0)
    chunk_count = Column(Integer, nullable=False, default=0)
    embedded_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class IngestionJob(Base):
    """Tracks background ingestion job statuses."""

    __tablename__ = "ingestion_jobs"

    id = Column(String, primary_key=True, doc="UUID hex string for the job")
    user_id = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="pending", doc="pending | processing | completed | failed")
    result_json = Column(Text, nullable=True, doc="JSON-serialized UploadResponse on success")
    error = Column(Text, nullable=True, doc="Error message on failure")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
