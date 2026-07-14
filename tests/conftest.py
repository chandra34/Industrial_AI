import sys
import os
from unittest.mock import MagicMock, patch

# Ensure the backend is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Pre-mock Redis and RQ before any backend imports to prevent connection errors
mock_redis_module = MagicMock()
mock_redis_client = MagicMock()
mock_redis_client.ping.return_value = True
mock_redis_module.Redis.from_url.return_value = mock_redis_client
mock_redis_module.from_url.return_value = mock_redis_client
mock_redis_module.Redis = MagicMock(return_value=mock_redis_client)
sys.modules["redis"] = mock_redis_module

mock_rq_module = MagicMock()
mock_queue = MagicMock()
mock_rq_module.Queue.return_value = mock_queue
sys.modules["rq"] = mock_rq_module
sys.modules["rq.serializers"] = MagicMock()

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from backend.database.models import Base
from backend.api.dependencies import get_db as dep_get_db
from backend.database.session import get_db as session_get_db
from backend.api.auth import get_current_user, FirebaseUser
from backend.config.settings import get_settings, Settings
from tests.mock_providers import MockEmbeddingProvider, MockLLMProvider, MockMilvusStore
from pathlib import Path

DB_FILE = Path("test_temp.db")
# Create SQLite engine for tests using a temporary file
engine = create_async_engine(f"sqlite+aiosqlite:///{DB_FILE}", connect_args={"check_same_thread": False})
TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)


@pytest.fixture(scope="session", autouse=True)
def setup_mock_environment():
    """Global session-scoped fixture to patch third-party service creation on startup.
    
    When RAG_EVAL=1 is set, all mocking is skipped so that evaluation tests
    can use real embedding, LLM, and Milvus services.
    """
    if os.environ.get("RAG_EVAL"):
        yield
        return

    mock_reranker = MagicMock()
    mock_parser = MagicMock()
    
    # Mock parse method to return list of ChunkRecord objects
    from backend.rag.chunking import ChunkRecord
    mock_parser.parse.return_value = [
        ChunkRecord(
            document_id="mock-doc-id",
            source_filename="mock-file.pdf",
            page_number=1,
            chunk_index=0,
            text="Mocked chunk text for testing document parsing.",
        )
    ]
    
    with patch("backend.rag.embeddings.EmbeddingFactory.create", side_effect=lambda s: MockEmbeddingProvider(s)), \
         patch("backend.rag.llm.LLMFactory.create", side_effect=lambda s: MockLLMProvider(s)), \
         patch("backend.vectordb.milvus_db.MilvusStore", side_effect=lambda s: MockMilvusStore(s)), \
         patch("backend.services.reranker_service.RerankerService", return_value=mock_reranker), \
         patch("backend.services.ingest_service.get_parser", return_value=mock_parser):
        yield


@pytest.fixture(scope="function")
async def db_session():
    """Fixture providing an isolated SQLite database session."""
    # Ensure any residual DB file is cleaned up first
    if DB_FILE.exists():
        try:
            DB_FILE.unlink()
        except Exception:
            pass
            
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async with TestingSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
            
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        
    if DB_FILE.exists():
        try:
            DB_FILE.unlink()
        except Exception:
            pass


@pytest.fixture(scope="function")
def mock_firebase_user():
    """Fixture providing a mock authenticated FirebaseUser."""
    return FirebaseUser(uid="test-user-123", email="test@example.com")


@pytest.fixture(scope="function")
async def app_client(db_session, mock_firebase_user):
    """Fixture providing a FastAPI TestClient with overrides."""
    from backend.main import app

    async def _override_get_db():
        yield db_session

    def _override_get_current_user():
        return mock_firebase_user

    app.dependency_overrides[dep_get_db] = _override_get_db
    app.dependency_overrides[session_get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user

    # Point backend settings database_url to our test_temp.db to make sure startup tables are created on it
    settings = get_settings()
    with patch.object(settings, "database_url", f"sqlite:///{DB_FILE}"):
        with TestClient(app) as client:
            yield client

    app.dependency_overrides.clear()
