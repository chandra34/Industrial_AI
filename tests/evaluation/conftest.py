"""
Evaluation-specific pytest fixtures.

Provides session-scoped services (real Milvus, embedding, LLM, retrieval, pipeline)
and the golden dataset as fixtures for evaluation tests.
"""

import json
import logging
import os
from pathlib import Path

import pytest

from backend.config.settings import Settings
from backend.rag.embeddings import EmbeddingFactory
from backend.rag.llm import LLMFactory
from backend.rag.pipeline import RAGPipeline
from backend.rag.retrieval import RetrievalService
from backend.vectordb.milvus_db import MilvusStore
from tests.evaluation.ingest_eval_docs import (
    get_eval_settings,
    ingest_eval_documents,
    EVAL_USER_ID,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Guard: Evaluation tests require RAG_EVAL=1 to run
# ---------------------------------------------------------------------------

def pytest_collection_modifyitems(config, items):
    """Skip all evaluation tests unless RAG_EVAL=1 is set."""
    if os.environ.get("RAG_EVAL"):
        return
    skip_marker = pytest.mark.skip(reason="RAG_EVAL env var not set. Skipping evaluation tests.")
    for item in items:
        item.add_marker(skip_marker)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def eval_settings() -> Settings:
    """Return Settings configured for the isolated eval_collection."""
    return get_eval_settings()


@pytest.fixture(scope="function")
async def eval_vector_store(eval_settings) -> MilvusStore:
    """Set up the evaluation Milvus collection with ingested documents."""
    return await ingest_eval_documents(eval_settings)


@pytest.fixture(scope="session")
def eval_embedding_service(eval_settings):
    """Return a real embedding provider for evaluation."""
    return EmbeddingFactory.create(eval_settings)


@pytest.fixture(scope="session")
def eval_llm_service(eval_settings):
    """Return a real LLM provider for evaluation."""
    return LLMFactory.create(eval_settings)


@pytest.fixture(scope="function")
async def eval_retrieval_service(eval_settings, eval_vector_store, eval_embedding_service, eval_llm_service):
    """Return a real RetrievalService wired to the eval collection."""
    return RetrievalService(
        settings=eval_settings,
        vector_store=eval_vector_store,
        embedding_service=eval_embedding_service,
        reranker_service=None,
        llm_service=eval_llm_service,
    )


@pytest.fixture(scope="function")
async def eval_rag_pipeline(eval_settings, eval_retrieval_service, eval_llm_service):
    """Return a real RAGPipeline wired to the eval collection."""
    return RAGPipeline(
        settings=eval_settings,
        retrieval_service=eval_retrieval_service,
        llm_service=eval_llm_service,
    )


@pytest.fixture(scope="session")
def golden_dataset() -> list[dict]:
    """Load and return the golden dataset test cases."""
    dataset_path = Path(__file__).resolve().parent.parent / "golden_dataset.json"
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def eval_user_id() -> str:
    """Return the evaluation user ID used during document ingestion."""
    return EVAL_USER_ID
