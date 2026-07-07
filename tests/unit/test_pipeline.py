import pytest
from unittest.mock import patch, MagicMock

from backend.config.settings import get_settings
from backend.rag.pipeline import RAGPipeline, QAResult
from backend.rag.retrieval import RetrievedChunk
from backend.schemas.safety import SafetyReviewReport, PTWReviewRequest

@pytest.fixture
def pipeline_setup():
    settings = get_settings()
    retrieval_service = MagicMock()
    llm_service = MagicMock()
    
    pipeline = RAGPipeline(
        settings=settings,
        retrieval_service=retrieval_service,
        llm_service=llm_service
    )
    return pipeline, settings, retrieval_service, llm_service


@pytest.mark.asyncio
async def test_pipeline_answer_question(pipeline_setup):
    """Test standard Q&A execution path."""
    pipeline, settings, retrieval_service, llm_service = pipeline_setup
    
    # Mock retrieval to return context documents
    mock_chunk = RetrievedChunk(
        document_id="doc-1",
        source_filename="safety_rule.pdf",
        page_number=2,
        chunk_index=0,
        chunk_text="Wear gloves when handling chemical valves.",
        score=0.9
    )
    
    async def mock_search(*args, **kwargs):
        return [mock_chunk]
    retrieval_service.search.side_effect = mock_search
    
    # Mock LLM to return answer text
    async def mock_generate_answer(messages):
        return "You must wear gloves according to safety_rule.pdf page 2."
    llm_service.generate_answer.side_effect = mock_generate_answer
    
    result = await pipeline.answer_question(
        question="Should I wear gloves at valve 3?",
        user_id="user-123",
        top_k=3
    )
    
    assert isinstance(result, QAResult)
    assert result.answer == "You must wear gloves according to safety_rule.pdf page 2."
    assert len(result.sources) == 1
    assert result.sources[0].source_filename == "safety_rule.pdf"
    
    retrieval_service.search.assert_called_once_with(
        "Should I wear gloves at valve 3?",
        user_id="user-123",
        top_k=3
    )


@pytest.mark.asyncio
async def test_pipeline_review_permit(pipeline_setup):
    """Test structured permit review execution path."""
    pipeline, settings, retrieval_service, llm_service = pipeline_setup
    
    mock_chunk = RetrievedChunk(
        document_id="doc-2",
        source_filename="sop_loto.pdf",
        page_number=5,
        chunk_index=3,
        chunk_text="Isolate discharge valve before line open.",
        score=0.88
    )
    
    async def mock_search(*args, **kwargs):
        return [mock_chunk]
    retrieval_service.search.side_effect = mock_search
    
    # Mock LLM structured output to return JSON string validating SafetyReviewReport
    mock_report_json = (
        '{"status": "Needs Review", "summary": "LOTO steps missing discharge valve isolation.", '
        '"findings": [{"severity": "High", "finding_type": "Missing Lockout/Isolation", '
        '"description": "Discharge valve LOTO missing.", "recommendation": "Isolate discharge valve.", '
        '"reference_source": "sop_loto.pdf page 5"}]}'
    )
    async def mock_generate_structured_output(*args, **kwargs):
        return mock_report_json
    llm_service.generate_structured_output.side_effect = mock_generate_structured_output
    
    request = PTWReviewRequest(
        permit_text="Line break procedure: wear face shield, isolate suction valve.",
        equipment="centrifugal pump",
        manufacturer="siemens"
    )
    
    report = await pipeline.review_permit(request, user_id="user-123")
    
    assert isinstance(report, SafetyReviewReport)
    assert report.status == "Needs Review"
    assert len(report.findings) == 1
    assert report.findings[0].severity == "High"
    assert report.findings[0].finding_type == "Missing Lockout/Isolation"
    
    retrieval_service.search.assert_called_once()
    called_kwargs = retrieval_service.search.call_args[1]
    assert called_kwargs["query"] == request.permit_text
    assert called_kwargs["user_id"] == "user-123"


@pytest.mark.asyncio
async def test_pipeline_context_truncation(pipeline_setup):
    """Test that context documents are truncated below settings.max_context_chars."""
    pipeline, settings, retrieval_service, llm_service = pipeline_setup
    
    # Set context limit low for testing
    settings.max_context_chars = 200
    
    chunk1 = RetrievedChunk(
        document_id="d1", source_filename="f1.pdf", page_number=1, chunk_index=0,
        chunk_text="A" * 100, score=0.9
    )
    chunk2 = RetrievedChunk(
        document_id="d2", source_filename="f2.pdf", page_number=1, chunk_index=0,
        chunk_text="B" * 100, score=0.8
    )
    
    async def mock_search(*args, **kwargs):
        return [chunk1, chunk2]
    retrieval_service.search.side_effect = mock_search
    
    captured_messages = []
    async def mock_generate_answer(messages):
        nonlocal captured_messages
        captured_messages = messages
        return "Answer"
    llm_service.generate_answer.side_effect = mock_generate_answer
    
    await pipeline.answer_question(question="Q", user_id="u")
    
    # Verify that only the first chunk was included due to limit constraints
    user_message = captured_messages[1]["content"]
    assert "f1.pdf" in user_message
    assert "f2.pdf" not in user_message
