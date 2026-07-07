import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import numpy as np

from backend.config.settings import get_settings
from backend.rag.retrieval import RetrievalService, RetrievedChunk
from backend.vectordb.reads import VectorSearchHit
from tests.mock_providers import MockEmbeddingProvider, MockLLMProvider, MockMilvusStore

@pytest.fixture
def retrieval_setup():
    settings = get_settings()
    vector_store = MockMilvusStore(settings)
    embedding_service = MockEmbeddingProvider(settings)
    llm_service = MockLLMProvider(settings)
    reranker_service = AsyncMock()
    
    # Disable reranker and bm25 by default to isolate basic dense search tests
    settings.reranker_enabled = False
    settings.bm25_enabled = False
    
    service = RetrievalService(
        settings=settings,
        vector_store=vector_store,
        embedding_service=embedding_service,
        reranker_service=reranker_service,
        llm_service=llm_service
    )
    return service, settings, vector_store, embedding_service, llm_service, reranker_service


@pytest.mark.asyncio
async def test_retrieval_basic_dense(retrieval_setup):
    """Test standard dense search with mapping to RetrievedChunk."""
    service, settings, vector_store, embedding_service, llm_service, _ = retrieval_setup
    
    # Mock vector store search hits
    mock_hit = VectorSearchHit(
        document_id="doc-1",
        source_filename="manual_1.pdf",
        page_number=3,
        chunk_index=0,
        chunk_text="This is standard pump manual content.",
        score=0.85,
        manufacturer="siemens",
        equipment="pump"
    )
    vector_store.search_results = [mock_hit]
    
    # Pass metadata_filter explicitly to bypass intent extraction for basic test
    results = await service.search(
        query="siemens pump",
        user_id="user-123",
        top_k=5,
        metadata_filter='manufacturer == "siemens"'
    )
    
    assert len(results) == 1
    chunk = results[0]
    assert isinstance(chunk, RetrievedChunk)
    assert chunk.document_id == "doc-1"
    assert chunk.chunk_text == "This is standard pump manual content."
    assert chunk.score == 0.85
    assert chunk.manufacturer == "siemens"


@pytest.mark.asyncio
async def test_retrieval_hybrid(retrieval_setup):
    """Test that hybrid search is called when bm25 is enabled."""
    service, settings, vector_store, _, _, _ = retrieval_setup
    settings.bm25_enabled = True
    
    mock_hit = VectorSearchHit(
        document_id="doc-2",
        source_filename="manual_2.pdf",
        page_number=5,
        chunk_index=1,
        chunk_text="This is hybrid text search matching.",
        score=0.9,
        manufacturer="siemens",
        equipment="turbine"
    )
    vector_store.search_results = [mock_hit]
    
    # Spy on vector store hybrid search
    with patch.object(vector_store, "hybrid_search", wraps=vector_store.hybrid_search) as spy_hybrid:
        results = await service.search(
            query="siemens turbine LOTO",
            user_id="user-123",
            top_k=2,
            metadata_filter='equipment == "turbine"'
        )
        assert len(results) == 1
        spy_hybrid.assert_called_once()


@pytest.mark.asyncio
async def test_retrieval_intent_extraction(retrieval_setup):
    """Test that query intent is extracted via LLM if metadata filter is not provided."""
    service, settings, vector_store, _, llm_service, _ = retrieval_setup
    
    # Configure mock LLM to return extracted manufacturer and equipment
    llm_service.structured_response = {
        "manufacturer": "Siemens",
        "equipment": "Centrifugal Pump"
    }
    
    # Mock vector store search to return a hit (avoids triggering fallback search)
    mock_hit = VectorSearchHit(
        document_id="doc-1",
        source_filename="manual_1.pdf",
        page_number=3,
        chunk_index=0,
        chunk_text="Some chunk",
        score=0.85
    )
    vector_store.search_results = [mock_hit]
    
    with patch.object(vector_store, "search", wraps=vector_store.search) as spy_search:
        await service.search(
            query="How to isolate Siemens Centrifugal Pump?",
            user_id="user-123",
            top_k=3
        )
        
        # Verify search was called with compiled metadata filter string
        spy_search.assert_called_once()
        called_args, called_kwargs = spy_search.call_args
        assert "metadata_filter" in called_kwargs
        assert called_kwargs["metadata_filter"] == 'manufacturer == "siemens" and equipment == "centrifugal pump"'


@pytest.mark.asyncio
async def test_retrieval_fallback(retrieval_setup):
    """Test that retrieval falls back to unfiltered search if filtered search returns 0 hits."""
    service, settings, vector_store, _, _, _ = retrieval_setup
    
    # Return empty list when filtered, but return hits when unfiltered
    mock_hit = VectorSearchHit(
        document_id="doc-4",
        source_filename="fallback.pdf",
        page_number=1,
        chunk_index=0,
        chunk_text="Unfiltered fallback match content.",
        score=0.7
    )
    
    async def mock_search(query_embedding, top_k, user_id, metadata_filter=None):
        if metadata_filter is not None:
            return []  # Filtered returns nothing
        return [mock_hit]  # Unfiltered returns a hit
        
    with patch.object(vector_store, "search", side_effect=mock_search) as spy_search:
        results = await service.search(
            query="non-existent pump model safety isolation",
            user_id="user-123",
            top_k=3,
            metadata_filter='equipment == "non-existent-pump"'
        )
        
        # Verify search was called twice (first with filter, then fallback with None)
        assert spy_search.call_count == 2
        
        first_call_kwargs = spy_search.call_args_list[0][1]
        assert first_call_kwargs["metadata_filter"] == 'equipment == "non-existent-pump"'
        
        second_call_kwargs = spy_search.call_args_list[1][1]
        assert second_call_kwargs["metadata_filter"] is None
        
        assert len(results) == 1
        assert results[0].chunk_text == "Unfiltered fallback match content."


@pytest.mark.asyncio
async def test_retrieval_reranking(retrieval_setup):
    """Test that retrieved chunks are reordered by the RerankerService when enabled."""
    service, settings, vector_store, _, _, reranker_service = retrieval_setup
    settings.reranker_enabled = True
    
    # Mock raw search hits
    hit1 = VectorSearchHit(
        document_id="doc-1", source_filename="f.pdf", page_number=1,
        chunk_index=0, chunk_text="Chunk 1", score=0.8
    )
    hit2 = VectorSearchHit(
        document_id="doc-1", source_filename="f.pdf", page_number=1,
        chunk_index=1, chunk_text="Chunk 2", score=0.7
    )
    vector_store.search_results = [hit1, hit2]
    
    # Mock rerank output to reverse the order (since rerank is async, we mock return_value)
    reranker_service.rerank.return_value = [
        RetrievedChunk(document_id="doc-1", source_filename="f.pdf", page_number=1, chunk_index=1, chunk_text="Chunk 2", score=0.7),
        RetrievedChunk(document_id="doc-1", source_filename="f.pdf", page_number=1, chunk_index=0, chunk_text="Chunk 1", score=0.8)
    ]
    
    results = await service.search(
        query="test query",
        user_id="user-123",
        top_k=2,
        metadata_filter=None
    )
    
    # Verify reranker was called
    reranker_service.rerank.assert_called_once()
    
    # Order should be reversed (Chunk 2, then Chunk 1)
    assert len(results) == 2
    assert results[0].chunk_text == "Chunk 2"
    assert results[1].chunk_text == "Chunk 1"
