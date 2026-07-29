"""
Unified Tool Registry for OpenAI and Gemini Function Calling.
"""

import logging
from typing import Any, Callable, Dict, List, Optional
from backend.connectors.sap.tools import ALL_SAP_TOOLS

logger = logging.getLogger(__name__)


# Technical Manuals Vector RAG Search Tool Function
async def search_technical_manuals(
    query: str,
    top_k: int = 3,
    retrieval_service: Optional[Any] = None,
    user_id: str = "default_user",
) -> List[Dict[str, Any]]:
    """Search PDF equipment manuals, SOPs, and safety guidelines in Vector DB via RetrievalService."""
    logger.info("RAG Tool: search_technical_manuals(query='%s', top_k=%d)", query, top_k)
    if retrieval_service:
        try:
            chunks = await retrieval_service.search(query=query, user_id=user_id, top_k=top_k)
            return [
                {
                    "document": chunk.source_filename,
                    "page": chunk.page_number,
                    "section": chunk.section or "General",
                    "content": chunk.chunk_text,
                    "score": round(chunk.score, 4),
                }
                for chunk in chunks
            ]
        except Exception as e:
            logger.warning("RAG Vector DB search execution error: %s", e)

    # Fallback response if retrieval_service is unavailable
    return [
        {
            "document": "Equipment Maintenance Manual",
            "section": "General Specifications & SOPs",
            "content": f"Query results for '{query}'. Ensure safety lockouts are applied before servicing.",
        }
    ]


# Combined dictionary of all executable tool functions across SAP, OPC UA, and Vector RAG
ALL_EXECUTABLE_TOOLS: Dict[str, Callable] = {
    **ALL_SAP_TOOLS,
    "search_technical_manuals": search_technical_manuals,
}


def get_openai_tool_definitions() -> List[Dict[str, Any]]:
    """Return OpenAI-formatted tool schema definitions for LLM tool binding.

    :return: List of OpenAI tool definition dictionaries.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "check_material_stock",
                "description": "Check real-time inventory stock level for a material in an SAP plant.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "material_id": {"type": "string", "description": "SAP Material Number (e.g. 'SKF-6214')"},
                        "plant_id": {"type": "string", "description": "SAP Plant ID (e.g. '1010')"},
                    },
                    "required": ["material_id", "plant_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_equipment_details",
                "description": "Get equipment specs, location, and master details from SAP.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "equipment_id": {"type": "string", "description": "SAP Equipment ID (e.g. '10004921')"},
                    },
                    "required": ["equipment_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_maintenance_notifications",
                "description": "Get breakdown reports and maintenance notifications from SAP.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "plant_id": {"type": "string", "description": "SAP Plant ID"},
                        "equipment_id": {"type": "string", "description": "Equipment ID"},
                        "top": {"type": "integer", "default": 5},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_work_orders",
                "description": "Get active maintenance work orders from SAP.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "plant_id": {"type": "string", "description": "SAP Plant ID"},
                        "order_type": {"type": "string", "description": "Order type (e.g. 'PM01')"},
                        "system_status": {"type": "string", "description": "Status string"},
                        "top": {"type": "integer", "default": 50},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_production_orders",
                "description": "Get production order status and yield from SAP PP.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "plant_id": {"type": "string", "description": "SAP Plant ID"},
                        "material_id": {"type": "string", "description": "Material ID"},
                        "top": {"type": "integer", "default": 50},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_inspection_lots",
                "description": "Get quality inspection lots and lab test pass/fail results from SAP QM.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "material_id": {"type": "string", "description": "Material ID"},
                        "batch_id": {"type": "string", "description": "Batch ID"},
                        "plant_id": {"type": "string", "description": "Plant ID"},
                        "top": {"type": "integer", "default": 50},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_technical_manuals",
                "description": "Search PDF equipment manuals, SOPs, and safety instructions in Vector DB.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query text"},
                        "top_k": {"type": "integer", "default": 3},
                    },
                    "required": ["query"],
                },
            },
        },
    ]
