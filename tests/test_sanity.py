from backend.database.models import Document, IngestionJob
from fastapi.testclient import TestClient

def test_db_sanity(db_session):
    """Verify that the in-memory SQLite database can create and query tables successfully."""
    # Create a test document record
    doc = Document(
        id="test-doc-id-123",
        user_id="test-user-123",
        filename="manual.pdf",
        stored_path="/path/to/manual.pdf",
        page_count=10,
        chunk_count=15,
        embedded_count=15,
        document_type="SOP",
        manufacturer="siemens",
        equipment="turbine",
    )
    db_session.add(doc)
    db_session.commit()

    # Query the document record
    retrieved_doc = db_session.query(Document).filter_by(id="test-doc-id-123").first()
    assert retrieved_doc is not None
    assert retrieved_doc.filename == "manual.pdf"
    assert retrieved_doc.manufacturer == "siemens"

    # Create an ingestion job record
    job = IngestionJob(
        id="test-job-id-456",
        user_id="test-user-123",
        status="pending",
    )
    db_session.add(job)
    db_session.commit()

    # Query the job record
    retrieved_job = db_session.query(IngestionJob).filter_by(id="test-job-id-456").first()
    assert retrieved_job is not None
    assert retrieved_job.status == "pending"


def test_health_route_sanity(app_client: TestClient):
    """Verify that the FastAPI health check endpoint is responsive and returns correct values."""
    response = app_client.get("/api/v1/health")
    assert response.status_code == 200
    
    data = response.json()
    assert "app_name" in data
    assert "milvus_collection" in data
    assert "llm_model" in data


def test_readiness_route_sanity(app_client: TestClient):
    """Verify that the deep readiness check endpoint resolves dependencies using mocks."""
    response = app_client.get("/api/v1/healthz/readiness")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "ok"
    assert data["redis"] == "ok"
    assert data["milvus"] == "ok"
