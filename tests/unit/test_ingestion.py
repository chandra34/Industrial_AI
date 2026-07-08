import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from backend.config.settings import get_settings
from backend.services.ingest_service import IngestService, IngestionResult
from backend.database.models import Document
from sqlalchemy.future import select
from tests.mock_providers import MockEmbeddingProvider, MockLLMProvider, MockMilvusStore

@pytest.fixture
def ingest_service():
    settings = get_settings()
    vector_store = MockMilvusStore(settings)
    embedding_service = MockEmbeddingProvider(settings)
    llm_service = MockLLMProvider(settings)
    return IngestService(settings, vector_store, embedding_service, llm_service)

@pytest.mark.asyncio
async def test_ingest_pdf_success(ingest_service, db_session):
    """Test standard ingestion success path."""
    pdf_bytes = b"%PDF-1.4 test data"
    filename = "test_manual.pdf"
    user_id = "test-user-123"
    metadata = {
        "document_type": "OEM Manual",
        "manufacturer": "Siemens",
        "equipment": "Centrifugal Pump",
        "revision": "Rev A",
        "language": "English"
    }

    result = await ingest_service.ingest_pdf(
        file_bytes=pdf_bytes,
        original_name=filename,
        user_id=user_id,
        db=db_session,
        metadata=metadata
    )

    assert isinstance(result, IngestionResult)
    assert result.document_id is not None
    assert result.filename == filename
    assert result.manufacturer == "siemens"  # Checks normalization
    assert result.equipment == "centrifugal pump"  # Checks normalization

    res = await db_session.execute(select(Document).filter(Document.id == result.document_id))
    doc_in_db = res.scalars().first()
    assert doc_in_db is not None
    assert doc_in_db.filename == filename
    assert doc_in_db.manufacturer == "siemens"

    # Cleanup the saved file on disk created during test
    stored_file = Path(result.stored_path)
    if stored_file.exists():
        stored_file.unlink()

@pytest.mark.asyncio
async def test_ingest_pdf_empty_file(ingest_service, db_session):
    """Test that ingestion rejects empty file bytes."""
    with pytest.raises(ValueError, match="Uploaded file is empty"):
        await ingest_service.ingest_pdf(
            file_bytes=b"",
            original_name="empty.pdf",
            user_id="test-user-123",
            db=db_session
        )

@pytest.mark.asyncio
async def test_ingest_pdf_metadata_fallback(ingest_service, db_session):
    """Test that fallback LLM metadata extraction is triggered for 'Unknown' fields."""
    pdf_bytes = b"%PDF-1.4 test data"
    filename = "test_manual.pdf"
    user_id = "test-user-123"
    
    metadata = {
        "document_type": "Unknown",
        "manufacturer": "Unknown",
        "equipment": "Unknown",
        "revision": "Unknown",
        "language": "English"
    }

    # Configure our MockLLMProvider to return specific structured outputs
    ingest_service.llm_service.structured_response = {
        "document_type": "SOP",
        "manufacturer": "Siemens",
        "equipment": "Gas Turbine",
        "revision": "V2.1",
        "language": "English"
    }

    # Ensure GROQ_API_KEY is considered configured in settings for LLM fallback
    with patch.object(ingest_service.settings, "groq_api_key", "mock-groq-key"):
        result = await ingest_service.ingest_pdf(
            file_bytes=pdf_bytes,
            original_name=filename,
            user_id=user_id,
            db=db_session,
            metadata=metadata
        )

    # Verify fields are updated from the LLM mocked response and normalized
    assert result.document_type == "SOP"
    assert result.manufacturer == "siemens"
    assert result.equipment == "gas turbine"
    assert result.revision == "V2.1"

    # Cleanup test upload
    stored_file = Path(result.stored_path)
    if stored_file.exists():
        stored_file.unlink()

@pytest.mark.asyncio
async def test_ingest_pdf_failure_cleanup(ingest_service, db_session):
    """Test that file and vector cleanups are triggered on exception."""
    pdf_bytes = b"%PDF-1.4 test data"
    filename = "test_manual_fail.pdf"
    user_id = "test-user-123"

    # Force insert_chunks to raise an error during storage phase
    async def mock_insert_raise(*args, **kwargs):
        raise RuntimeError("Vector database insertion failed!")

    with patch.object(ingest_service.vector_store, "insert_chunks", side_effect=mock_insert_raise):
        with pytest.raises(RuntimeError, match="Vector database insertion failed!"):
            await ingest_service.ingest_pdf(
                file_bytes=pdf_bytes,
                original_name=filename,
                user_id=user_id,
                db=db_session
            )

    # Verify that the vector_store was told to clean up/delete the document
    assert len(ingest_service.vector_store.deleted_documents) > 0
    doc_id, uid = ingest_service.vector_store.deleted_documents[0]
    assert uid == user_id

    # Verify that no file exists in upload dir matching the failed document_id
    upload_dir = Path(ingest_service.settings.resolved_upload_dir)
    files = list(upload_dir.glob(f"{doc_id}_*"))
    assert len(files) == 0
