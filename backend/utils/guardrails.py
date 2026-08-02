"""
Production guardrails for the Industrial AI Agent platform.

Provides three layers of protection:
1. Input sanitization — blocks prompt injection attempts.
2. Tool execution gating — enforces a read-only tool whitelist.
3. Output grounding — verifies LLM answers against retrieved source context.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom Exception
# ---------------------------------------------------------------------------

class GuardrailViolationError(Exception):
    """Raised when any guardrail check fails."""

    def __init__(self, violation_type: str, detail: str) -> None:
        self.violation_type = violation_type
        self.detail = detail
        super().__init__(f"[{violation_type}] {detail}")


# ---------------------------------------------------------------------------
# Layer 1: Input Sanitization
# ---------------------------------------------------------------------------

# Patterns that indicate prompt injection or privilege escalation attempts.
# Case-insensitive matching. Add new patterns as threats evolve.
_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"ignore\s+(all\s+)?above\s+instructions",
        r"you\s+are\s+now\s+(in\s+)?DAN\s+mode",
        r"bypass\s+(safety|guardrail|security)",
        r"override\s+system\s+prompt",
        r"act\s+as\s+an?\s+(unrestricted|unfiltered)",
        r"disregard\s+(your|the)\s+(rules|guidelines|instructions)",
        r"execute\s+shell\s+command",
        r"run\s+(this\s+)?sql",
        r"drop\s+table",
        r"delete\s+from",
        r"rm\s+-rf",
    ]
]

# Maximum allowed query length (chars). Blocks excessively long prompt-stuffing attacks.
MAX_QUERY_LENGTH = 4000


def validate_input(query: str) -> str:
    """Validate and sanitize an incoming user query.

    :param query: Raw user query string.
    :return: Cleaned query string.
    :raises GuardrailViolationError: If injection patterns are detected or query is invalid.
    """
    if not query or not query.strip():
        raise GuardrailViolationError("INPUT", "Query is empty.")

    clean = query.strip()

    if len(clean) > MAX_QUERY_LENGTH:
        raise GuardrailViolationError(
            "INPUT",
            f"Query exceeds maximum allowed length ({MAX_QUERY_LENGTH} chars).",
        )

    for pattern in _INJECTION_PATTERNS:
        if pattern.search(clean):
            logger.warning(
                "Input guardrail triggered: prompt injection pattern detected — '%s'",
                pattern.pattern,
            )
            raise GuardrailViolationError(
                "INPUT",
                "Query contains disallowed instructions. Please rephrase your question.",
            )

    return clean


# ---------------------------------------------------------------------------
# Layer 2: Tool Execution Whitelist
# ---------------------------------------------------------------------------

# Only these tools may be executed by the orchestrator.
# Every tool listed here is strictly a read/lookup operation.
ALLOWED_TOOLS: frozenset[str] = frozenset({
    # SAP ERP (read-only queries)
    "check_material_stock",
    "get_material_master",
    "get_bill_of_materials",
    "get_equipment_details",
    "get_maintenance_notifications",
    "get_work_orders",
    "get_production_orders",
    "get_production_order_operations",
    "get_inspection_lots",
    "get_quality_notifications",
    # OPC UA (read-only telemetry)
    "browse_opcua_nodes",
    "search_opcua_nodes",
    "read_opcua_node_value",
    "read_opcua_node_details",
    # RAG Vector DB (read-only search)
    "search_technical_manuals",
})


def check_tool_allowed(tool_name: str) -> bool:
    """Check whether a tool name is in the read-only whitelist.

    :param tool_name: Name of the tool the LLM wants to execute.
    :return: True if allowed, False if blocked.
    """
    allowed = tool_name in ALLOWED_TOOLS
    if not allowed:
        logger.warning(
            "Tool guardrail blocked execution of non-whitelisted tool: '%s'",
            tool_name,
        )
    return allowed


# ---------------------------------------------------------------------------
# Layer 3: Output Grounding Verifier
# ---------------------------------------------------------------------------

# Regex to extract standalone numerical values (integers and decimals) from text.
_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")


def verify_grounding(
    answer: str,
    source_texts: list[str],
    *,
    threshold: float = 0.5,
) -> tuple[bool, Optional[str]]:
    """Verify that numerical claims in the answer are grounded in source context.

    Extracts all standalone numbers from the answer and checks what fraction
    appear in the combined source text. If the fraction falls below ``threshold``,
    the answer is considered ungrounded.

    :param answer: LLM-generated answer text.
    :param source_texts: List of retrieved chunk texts used as context.
    :param threshold: Minimum fraction of answer-numbers that must appear in sources.
    :return: Tuple of (is_grounded: bool, warning_message: str | None).
    """
    answer_numbers = set(_NUMBER_RE.findall(answer))
    if not answer_numbers:
        # No numerical claims to verify
        return True, None

    combined_sources = " ".join(source_texts)
    source_numbers = set(_NUMBER_RE.findall(combined_sources))

    grounded = answer_numbers & source_numbers
    ungrounded = answer_numbers - source_numbers

    # Filter out trivially common numbers (single digits, page numbers, etc.)
    significant_ungrounded = {n for n in ungrounded if len(n) >= 2 or float(n) >= 10}

    if not significant_ungrounded:
        return True, None

    grounded_ratio = len(grounded) / len(answer_numbers) if answer_numbers else 1.0

    if grounded_ratio < threshold:
        warning = (
            f"Grounding check warning: {len(significant_ungrounded)} numerical value(s) "
            f"in the answer are not found in source context: {significant_ungrounded}"
        )
        logger.warning(warning)
        return False, warning

    return True, None
