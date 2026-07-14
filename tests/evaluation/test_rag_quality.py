"""
RAG Quality Evaluation Test Suite.

Measures retrieval quality (Hit Rate, MRR) and generation quality
(Faithfulness, Answer Relevance) against the golden dataset.

Run with:
    $env:RAG_EVAL="1"; pytest tests/evaluation/ -s

The test asserts that average quality scores meet production thresholds.
A detailed Markdown report is written to tests/evaluation/run_report.md.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from backend.rag.pipeline import RAGPipeline
from backend.rag.retrieval import RetrievalService, RetrievedChunk
from backend.rag.llm import LLMProvider

logger = logging.getLogger(__name__)

REPORT_PATH = Path(__file__).resolve().parent / "run_report.md"

# ---------------------------------------------------------------------------
# Quality Thresholds
# ---------------------------------------------------------------------------

RETRIEVAL_HIT_RATE_THRESHOLD = 0.85       # 85%
GENERATION_FAITHFULNESS_THRESHOLD = 4.0   # out of 5
GENERATION_RELEVANCE_THRESHOLD = 4.0      # out of 5


# ---------------------------------------------------------------------------
# LLM-as-a-Judge Grading Schema
# ---------------------------------------------------------------------------

class GraderResponse(BaseModel):
    """Structured response from the LLM grader."""

    model_config = {"extra": "forbid"}

    faithfulness_score: int = Field(
        description="Score from 1 to 5. 5 = every fact in the answer is directly supported by the context. "
                    "1 = the answer contains significant unsupported claims or hallucinations."
    )
    faithfulness_explanation: str = Field(
        description="Brief explanation of why this faithfulness score was given."
    )
    relevance_score: int = Field(
        description="Score from 1 to 5. 5 = the answer completely and accurately addresses the question, "
                    "matching the ground truth answer. 1 = the answer is irrelevant or incorrect."
    )
    relevance_explanation: str = Field(
        description="Brief explanation of why this relevance score was given."
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_filename(source_filename: str, document_id: str) -> str:
    """Strip the document_id prefix from source_filename to get the original name."""
    if source_filename and document_id and source_filename.startswith(f"{document_id}_"):
        return source_filename[len(document_id) + 1:]
    return source_filename or ""


# Module-level dictionary to share retrieval scores with the generation report generator
_retrieval_results_cache = {
    "results": [],
    "avg_hit_rate": 0.0,
    "avg_mrr": 0.0
}


def _normalize_filename(name: str) -> str:
    """Normalize a PDF filename to be tolerant of minor typos (e.g. double 't' or symbols)."""
    norm = name.lower().strip()
    if norm.endswith(".pdf"):
        norm = norm[:-4]
    norm = norm.replace("_", "").replace("-", "")
    # Correct the specific typo "tenderdocumentt" in the golden dataset to match "tenderdocument"
    if norm == "tenderdocumentt":
        return "tenderdocument"
    return norm


def _check_retrieval_hit(
    chunks: list[RetrievedChunk],
    expected_document: str,
    expected_page: int | None,
) -> tuple[bool, float]:
    """Check if the expected document/page appears in retrieved chunks.

    Returns:
        (hit: bool, reciprocal_rank: float)
    """
    if expected_page is None:
        # out_of_scope cases — skip retrieval scoring
        return False, 0.0

    norm_expected = _normalize_filename(expected_document)

    for rank, chunk in enumerate(chunks, start=1):
        clean_name = _clean_filename(chunk.source_filename, chunk.document_id)
        norm_clean = _normalize_filename(clean_name)
        
        # Typo-tolerant and case-insensitive matching
        if norm_clean == norm_expected and chunk.page_number == expected_page:
            return True, 1.0 / rank

    return False, 0.0


GRADER_PROMPT = """\
You are an expert evaluation grader for a Retrieval-Augmented Generation (RAG) system.

You are given:
1. The original **Question** asked by the user.
2. The **Retrieved Context** chunks that were provided to the RAG system.
3. The RAG system's **Generated Answer**.
4. The **Ground Truth Answer** (the correct reference answer).

Your task is to evaluate the Generated Answer on two dimensions:

**Faithfulness** (1-5): Is every factual claim in the Generated Answer directly supported by the Retrieved Context?
- 5: Completely faithful. Every claim is grounded in the context.
- 3: Mostly faithful but contains minor unsupported details.
- 1: Contains significant hallucinations or unsupported claims.

**Answer Relevance** (1-5): Does the Generated Answer correctly and completely answer the Question, compared to the Ground Truth?
- 5: Perfectly matches the ground truth meaning. Complete and accurate.
- 3: Partially correct. Addresses the question but misses key details.
- 1: Completely wrong, irrelevant, or fails to answer the question.

Respond with a JSON object matching the required schema.
"""


async def _grade_answer(
    llm_service: LLMProvider,
    query: str,
    context_text: str,
    generated_answer: str,
    ground_truth_answer: str,
) -> GraderResponse:
    """Use the LLM as a judge to grade the generated answer."""
    user_message = (
        f"**Question:** {query}\n\n"
        f"**Retrieved Context:**\n{context_text}\n\n"
        f"**Generated Answer:** {generated_answer}\n\n"
        f"**Ground Truth Answer:** {ground_truth_answer}"
    )
    messages = [
        {"role": "system", "content": GRADER_PROMPT},
        {"role": "user", "content": user_message},
    ]
    raw = await llm_service.generate_structured_output(
        messages=messages,
        response_model=GraderResponse,
        temperature=0.0,
    )
    return GraderResponse.model_validate_json(raw)


def _build_context_text(chunks: list[RetrievedChunk], max_chars: int = 6000) -> str:
    """Concatenate retrieved chunks into a text block for the grader prompt."""
    segments = []
    total = 0
    for chunk in chunks:
        segment = f"[{chunk.source_filename} | Page {chunk.page_number}]\n{chunk.chunk_text.strip()}\n"
        if total + len(segment) > max_chars:
            break
        segments.append(segment)
        total += len(segment)
    return "\n".join(segments) if segments else "(No context retrieved)"


# ---------------------------------------------------------------------------
# Report Generation
# ---------------------------------------------------------------------------

def _write_report(
    retrieval_results: list[dict],
    generation_results: list[dict],
    avg_hit_rate: float,
    avg_mrr: float,
    avg_faithfulness: float,
    avg_relevance: float,
    duration_seconds: float,
) -> None:
    """Write a detailed Markdown evaluation report."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "# RAG Evaluation Report",
        f"\n**Run Date:** {now}",
        f"**Total Duration:** {duration_seconds:.1f}s",
        f"**Test Cases:** {len(retrieval_results)} retrieval, {len(generation_results)} generation\n",
        "---\n",
        "## Summary Scores\n",
        "| Metric | Score | Threshold | Status |",
        "|--------|-------|-----------|--------|",
        f"| Retrieval Hit Rate | {avg_hit_rate:.1%} | {RETRIEVAL_HIT_RATE_THRESHOLD:.0%} | {'✅ PASS' if avg_hit_rate >= RETRIEVAL_HIT_RATE_THRESHOLD else '❌ FAIL'} |",
        f"| Retrieval MRR | {avg_mrr:.3f} | — | ℹ️ Info |",
        f"| Faithfulness | {avg_faithfulness:.2f}/5 | {GENERATION_FAITHFULNESS_THRESHOLD:.1f}/5 | {'✅ PASS' if avg_faithfulness >= GENERATION_FAITHFULNESS_THRESHOLD else '❌ FAIL'} |",
        f"| Answer Relevance | {avg_relevance:.2f}/5 | {GENERATION_RELEVANCE_THRESHOLD:.1f}/5 | {'✅ PASS' if avg_relevance >= GENERATION_RELEVANCE_THRESHOLD else '❌ FAIL'} |",
        "\n---\n",
        "## Retrieval Details\n",
        "| ID | Category | Query (truncated) | Expected Doc | Expected Page | Hit | MRR |",
        "|----|----------|-------------------|--------------|---------------|-----|-----|",
    ]
    for r in retrieval_results:
        q = r["query"][:50] + "..." if len(r["query"]) > 50 else r["query"]
        lines.append(
            f"| {r['id']} | {r['category']} | {q} | {r['expected_document']} | {r['expected_page']} | "
            f"{'✅' if r['hit'] else '❌'} | {r['mrr']:.2f} |"
        )

    lines.extend([
        "\n---\n",
        "## Generation Details\n",
    ])
    for g in generation_results:
        q = g["query"][:60] + "..." if len(g["query"]) > 60 else g["query"]
        lines.extend([
            f"### {g['id']} ({g['category']})",
            f"**Query:** {q}",
            f"**Faithfulness:** {g['faithfulness_score']}/5 — {g['faithfulness_explanation']}",
            f"**Relevance:** {g['relevance_score']}/5 — {g['relevance_explanation']}",
            f"**Generated Answer:** {g['generated_answer'][:200]}{'...' if len(g['generated_answer']) > 200 else ''}",
            "",
        ])

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Evaluation report written to %s", REPORT_PATH)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retrieval_quality(
    eval_retrieval_service: RetrievalService,
    golden_dataset: list[dict],
    eval_user_id: str,
):
    """Evaluate retrieval Hit Rate and MRR against the golden dataset.

    Skips 'out_of_scope' test cases where expected_page is null.
    """
    retrieval_results = []
    hits = 0
    mrr_sum = 0.0
    evaluated = 0

    for case in golden_dataset:
        # Skip out_of_scope cases for retrieval evaluation
        if case.get("expected_page") is None or case.get("category") == "out_of_scope":
            logger.info("Skipping retrieval eval for %s (out_of_scope)", case["id"])
            continue

        logger.info("Retrieval eval: %s — %s", case["id"], case["query"][:60])

        chunks = await eval_retrieval_service.search(
            query=case["query"],
            user_id=eval_user_id,
            top_k=5,
            metadata_filter=None,  # No metadata filter — rely on vector similarity
        )

        hit, mrr = _check_retrieval_hit(
            chunks,
            expected_document=case["expected_document"],
            expected_page=case["expected_page"],
        )

        retrieval_results.append({
            "id": case["id"],
            "category": case["category"],
            "query": case["query"],
            "expected_document": case["expected_document"],
            "expected_page": case["expected_page"],
            "hit": hit,
            "mrr": mrr,
            "retrieved_docs": [
                f"{_clean_filename(c.source_filename, c.document_id)} p{c.page_number}"
                for c in chunks
            ],
        })

        if hit:
            hits += 1
        mrr_sum += mrr
        evaluated += 1

    avg_hit_rate = hits / evaluated if evaluated > 0 else 0.0
    avg_mrr = mrr_sum / evaluated if evaluated > 0 else 0.0

    logger.info("Retrieval Hit Rate: %.1f%% (%d/%d)", avg_hit_rate * 100, hits, evaluated)
    logger.info("Retrieval MRR: %.3f", avg_mrr)

    # Store results for the report (will be used by test_generation_quality)
    _retrieval_results_cache["results"] = retrieval_results
    _retrieval_results_cache["avg_hit_rate"] = avg_hit_rate
    _retrieval_results_cache["avg_mrr"] = avg_mrr

    assert avg_hit_rate >= RETRIEVAL_HIT_RATE_THRESHOLD, (
        f"Retrieval Hit Rate {avg_hit_rate:.1%} is below threshold {RETRIEVAL_HIT_RATE_THRESHOLD:.0%}. "
        f"({hits}/{evaluated} queries hit the expected document/page)"
    )


@pytest.mark.asyncio
async def test_generation_quality(
    eval_rag_pipeline: RAGPipeline,
    eval_llm_service: LLMProvider,
    golden_dataset: list[dict],
    eval_user_id: str,
):
    """Evaluate generation Faithfulness and Relevance using LLM-as-a-Judge.

    After scoring, writes a detailed Markdown report to tests/evaluation/run_report.md.
    """
    start_time = time.time()
    generation_results = []
    faithfulness_scores = []
    relevance_scores = []

    for i, case in enumerate(golden_dataset):
        logger.info("Generation eval: %s — %s", case["id"], case["query"][:60])

        # Run full RAG pipeline
        qa_result = await eval_rag_pipeline.answer_question(
            question=case["query"],
            user_id=eval_user_id,
        )

        # Build context text from retrieved sources for grading
        context_text = _build_context_text(qa_result.sources)

        # Grade with LLM-as-a-Judge
        try:
            grade = await _grade_answer(
                llm_service=eval_llm_service,
                query=case["query"],
                context_text=context_text,
                generated_answer=qa_result.answer,
                ground_truth_answer=case["ground_truth_answer"],
            )
            f_score = max(1, min(5, grade.faithfulness_score))
            r_score = max(1, min(5, grade.relevance_score))
        except Exception as e:
            logger.error("Grading failed for %s: %s", case["id"], e)
            f_score = 1
            r_score = 1
            grade = GraderResponse(
                faithfulness_score=1,
                faithfulness_explanation=f"Grading failed: {e}",
                relevance_score=1,
                relevance_explanation=f"Grading failed: {e}",
            )

        faithfulness_scores.append(f_score)
        relevance_scores.append(r_score)

        generation_results.append({
            "id": case["id"],
            "category": case["category"],
            "query": case["query"],
            "generated_answer": qa_result.answer,
            "faithfulness_score": f_score,
            "faithfulness_explanation": grade.faithfulness_explanation,
            "relevance_score": r_score,
            "relevance_explanation": grade.relevance_explanation,
        })

        logger.info(
            "  %s: Faithfulness=%d/5, Relevance=%d/5",
            case["id"], f_score, r_score,
        )

        # Wait 30 seconds between queries to prevent Gemini rate limit/quota exhaustion
        if i < len(golden_dataset) - 1:
            logger.info("[EVAL] Waiting 30 seconds before next query to avoid Gemini rate limits...")
            await asyncio.sleep(30)
            logger.info("[EVAL] Wait complete. Proceeding to next query.")

    avg_faithfulness = sum(faithfulness_scores) / len(faithfulness_scores) if faithfulness_scores else 0.0
    avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0
    duration = time.time() - start_time

    logger.info("Avg Faithfulness: %.2f/5", avg_faithfulness)
    logger.info("Avg Relevance: %.2f/5", avg_relevance)
    logger.info("Generation evaluation completed in %.1fs", duration)

    # Retrieve retrieval results from the earlier test (if available)
    retrieval_results = _retrieval_results_cache["results"]
    avg_hit_rate = _retrieval_results_cache["avg_hit_rate"]
    avg_mrr = _retrieval_results_cache["avg_mrr"]

    # Write combined report
    _write_report(
        retrieval_results=retrieval_results,
        generation_results=generation_results,
        avg_hit_rate=avg_hit_rate,
        avg_mrr=avg_mrr,
        avg_faithfulness=avg_faithfulness,
        avg_relevance=avg_relevance,
        duration_seconds=duration,
    )

    assert avg_faithfulness >= GENERATION_FAITHFULNESS_THRESHOLD, (
        f"Avg Faithfulness {avg_faithfulness:.2f}/5 is below threshold {GENERATION_FAITHFULNESS_THRESHOLD:.1f}/5"
    )
    assert avg_relevance >= GENERATION_RELEVANCE_THRESHOLD, (
        f"Avg Relevance {avg_relevance:.2f}/5 is below threshold {GENERATION_RELEVANCE_THRESHOLD:.1f}/5"
    )
