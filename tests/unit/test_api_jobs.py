import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.database.models import IngestionJob
from backend.schemas.jobs import UploadJobAcceptedResponse, JobStatusResponse
from backend.config.settings import get_settings
from sqlalchemy.future import select

@pytest.fixture
def mock_fitz():
    """Mock PyMuPDF's fitz.open context manager."""
    mock_doc = MagicMock()
    mock_doc.page_count = 5
    mock_doc.__enter__.return_value = mock_doc
    mock_doc.__exit__.return_value = False
    with patch("fitz.open", return_value=mock_doc) as p:
        yield p, mock_doc


@pytest.mark.asyncio
async def test_api_upload_success(app_client: TestClient, db_session, mock_fitz):
    """Test that a valid PDF upload successfully initiates a background job."""
    file_payload = {"file": ("manual.pdf", b"%PDF-1.4 standard dummy bytes", "application/pdf")}
    metadata = {
        "document_type": "OEM Manual",
        "manufacturer": "siemens",
        "equipment": "turbine"
    }

    # Spy on the background RQ queue enqueuer
    with patch("backend.api.jobs.task_queue.enqueue") as mock_enqueue:
        response = app_client.post(
            "/api/v1/upload",
            files=file_payload,
            data=metadata
        )
        
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert "accepted" in data["message"].lower()

        # Check that job is recorded in SQLite
        job_id = data["job_id"]
        res = await db_session.execute(select(IngestionJob).filter(IngestionJob.id == job_id))
        job_record = res.scalars().first()
        assert job_record is not None
        assert job_record.status == "pending"

        # Check background enqueuer was triggered with job details
        mock_enqueue.assert_called_once()
        called_args = mock_enqueue.call_args[0]
        assert called_args[1] == job_id  # job_id passed to run_ingest_task


@pytest.mark.asyncio
async def test_api_upload_non_pdf(app_client: TestClient):
    """Test that uploading a non-PDF file returns a 400 Bad Request error."""
    file_payload = {"file": ("test.txt", b"plain text files are not supported", "text/plain")}
    response = app_client.post("/api/v1/upload", files=file_payload)
    
    assert response.status_code == 400
    assert "pdf" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_api_upload_size_limit(app_client: TestClient):
    """Test that files exceeding the maximum file size limit are rejected with 413."""
    file_payload = {"file": ("large_manual.pdf", b"x" * 1024 * 1024, "application/pdf")}
    
    # Temporarily set max upload to 0 MB to trigger validation failure
    settings = get_settings()
    with patch.object(settings, "max_upload_mb", 0):
        response = app_client.post("/api/v1/upload", files=file_payload)
        assert response.status_code == 413
        assert "size" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_api_upload_page_limit(app_client: TestClient, mock_fitz):
    """Test that PDFs exceeding the maximum page count limit are rejected with 413."""
    patch_open, mock_doc = mock_fitz
    
    # Configure the document page count to exceed the maximum allowed
    mock_doc.page_count = 1000
    file_payload = {"file": ("huge_doc.pdf", b"%PDF-1.4 dummy", "application/pdf")}
    
    response = app_client.post("/api/v1/upload", files=file_payload)
    assert response.status_code == 413
    assert "exceeds the maximum limit" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_api_job_status_retrieval(app_client: TestClient, db_session):
    """Test that job status retrieval endpoint matches actual database entries."""
    # Insert completed job record
    job_completed = IngestionJob(
        id="job-comp-1",
        user_id="test-user-123",
        status="completed",
        result_json='{"document_id": "d-1", "filename": "m.pdf", "stored_path": "/p", "page_count": 10, "chunk_count": 2, "embedded_count": 2}'
    )
    # Insert failed job record
    job_failed = IngestionJob(
        id="job-fail-2",
        user_id="test-user-123",
        status="failed",
        error="Database deadlock occurred during storage"
    )
    db_session.add(job_completed)
    db_session.add(job_failed)
    await db_session.commit()

    # Query completed job
    resp = app_client.get("/api/v1/jobs/job-comp-1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["result"]["document_id"] == "d-1"
    assert data["error"] is None

    # Query failed job
    resp = app_client.get("/api/v1/jobs/job-fail-2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "failed"
    assert "deadlock" in data["error"]
    assert data["result"] is None

    # Query non-existent job
    resp = app_client.get("/api/v1/jobs/job-missing-3")
    assert resp.status_code == 404
