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


from backend.connectors.opcua import OPCUAClient
from backend.connectors.opcua.browser import OPCUABrowser
from backend.connectors.opcua.reader import OPCUAReader


def _to_json_safe(val: Any) -> Any:
    """Convert custom OPC UA objects, datetimes, or bytes into JSON-serializable primitives."""
    if val is None or isinstance(val, (int, float, str, bool)):
        return val
    if isinstance(val, (list, tuple)):
        return [_to_json_safe(item) for item in val]
    if isinstance(val, dict):
        return {str(k): _to_json_safe(v) for k, v in val.items()}
    return str(val)


# OPC UA OT Sensor Telemetry Tool Functions
async def browse_opcua_nodes(
    node_id: Optional[str] = None,
    opcua_client: Optional[OPCUAClient] = None,
) -> List[Dict[str, Any]]:
    """Browse child nodes of an OPC UA node (defaults to Objects root folder if node_id is None)."""
    logger.info("OPC UA Tool: browse_opcua_nodes(node_id=%s)", node_id)
    if opcua_client:
        try:
            browser = OPCUABrowser(opcua_client)
            res = await browser.browse_children(node_id)
            return _to_json_safe(res)
        except Exception as e:
            logger.error("OPC UA browse_children error: %s", e)
            return [{"error": f"Failed to browse OPC UA nodes: {e}"}]
    return [{"node_id": "ns=2;i=1001", "browse_name": "Boiler_Line1", "node_class": "Object"}]


async def search_opcua_nodes(
    search_term: str,
    start_node_id: Optional[str] = None,
    opcua_client: Optional[OPCUAClient] = None,
) -> List[Dict[str, Any]]:
    """Search OPC UA node names matching a search keyword (e.g. 'vibration', 'temperature')."""
    logger.info("OPC UA Tool: search_opcua_nodes(search_term='%s')", search_term)
    if opcua_client:
        try:
            browser = OPCUABrowser(opcua_client)
            res = await browser.search_nodes(search_term, start_node_id)
            return _to_json_safe(res)
        except Exception as e:
            logger.error("OPC UA search_nodes error: %s", e)
            return [{"error": f"Failed to search OPC UA nodes: {e}"}]
    return [{"node_id": f"ns=2;s={search_term}", "browse_name": f"{search_term}_Sensor", "node_class": "Variable"}]


async def read_opcua_node_value(
    node_id: str,
    opcua_client: Optional[OPCUAClient] = None,
) -> Dict[str, Any]:
    """Read the live numerical sensor reading for an OPC UA node_id."""
    logger.info("OPC UA Tool: read_opcua_node_value(node_id='%s')", node_id)
    if opcua_client:
        try:
            reader = OPCUAReader(opcua_client)
            val = await reader.read_node_value(node_id)
            return {"node_id": node_id, "value": _to_json_safe(val)}
        except Exception as e:
            logger.error("OPC UA read_node_value error: %s", e)
            return {"node_id": node_id, "error": f"Failed to read OPC UA node value: {e}"}
    return {"node_id": node_id, "value": 87.5}


async def read_opcua_node_details(
    node_id: str,
    opcua_client: Optional[OPCUAClient] = None,
) -> Dict[str, Any]:
    """Read detailed OPC UA node telemetry metadata (value, status code, timestamps)."""
    logger.info("OPC UA Tool: read_opcua_node_details(node_id='%s')", node_id)
    if opcua_client:
        try:
            reader = OPCUAReader(opcua_client)
            res = await reader.read_node_details(node_id)
            return _to_json_safe(res)
        except Exception as e:
            logger.error("OPC UA read_node_details error: %s", e)
            return {"node_id": node_id, "error": f"Failed to read OPC UA node details: {e}"}
    return {
        "node_id": node_id,
        "browse_name": "Sensor",
        "value": 87.5,
        "status_code": "Good",
        "source_timestamp": "2026-07-29T22:00:00Z",
        "server_timestamp": "2026-07-29T22:00:00Z",
    }


# Combined dictionary of all executable tool functions across SAP, OPC UA, and Vector RAG
ALL_EXECUTABLE_TOOLS: Dict[str, Callable] = {
    **ALL_SAP_TOOLS,
    "search_technical_manuals": search_technical_manuals,
    "browse_opcua_nodes": browse_opcua_nodes,
    "search_opcua_nodes": search_opcua_nodes,
    "read_opcua_node_value": read_opcua_node_value,
    "read_opcua_node_details": read_opcua_node_details,
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
                "description": "Check real-time inventory stock level for a material in an SAP plant from SAP ERP. Do not use for live machine metrics or document deadlines.",
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
                "name": "get_material_master",
                "description": "Get material master specifications, description, dimensions, and base weight from SAP MM. Do not use for machine telemetry or document guidelines/deadlines.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "material_id": {"type": "string", "description": "SAP Material Number (e.g. 'MAT-001')"},
                    },
                    "required": ["material_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_bill_of_materials",
                "description": "Get Bill of Materials (BOM) sub-component breakdown for a material in an SAP plant.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "material_id": {"type": "string", "description": "Parent SAP Material Number"},
                        "plant_id": {"type": "string", "description": "SAP Plant ID (e.g. '1010')"},
                        "top": {"type": "integer", "default": 100},
                    },
                    "required": ["material_id", "plant_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_production_order_operations",
                "description": "Get shop floor operations, routing steps, and work center assignments for a specific SAP production order.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string", "description": "SAP Production Order Number (e.g. '1000214')"},
                        "top": {"type": "integer", "default": 100},
                    },
                    "required": ["order_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_quality_notifications",
                "description": "Get quality defect reports, customer complaints, and quality notifications from SAP QM.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "plant_id": {"type": "string", "description": "SAP Plant ID"},
                        "notification_type": {"type": "string", "description": "Notification type (e.g. 'Q1' internal defect, 'Q2' customer complaint)"},
                        "top": {"type": "integer", "default": 50},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_technical_manuals",
                "description": "Search PDF equipment manuals, SOPs, task deadlines, submission dates, project files, and safety instructions in Vector DB.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query text (e.g. 'lubrication frequency', 'task submission deadline')"},
                        "top_k": {"type": "integer", "default": 3},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "browse_opcua_nodes",
                "description": "Browse child nodes and folder hierarchy on the connected OPC UA server.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "node_id": {"type": "string", "description": "Optional parent OPC UA Node ID (e.g. 'ns=2;i=1001'). Omit for root Objects folder."},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_opcua_nodes",
                "description": "Search OPC UA node browse names for a tag or sensor keyword (e.g. 'vibration', 'temperature', 'boiler'). Do not use for document search or SAP material lookup.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "search_term": {"type": "string", "description": "Keyword search string"},
                        "start_node_id": {"type": "string", "description": "Optional starting node ID"},
                    },
                    "required": ["search_term"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_opcua_node_value",
                "description": "Read current live numerical or string value from an OPC UA sensor node ID. Do not use for business data, materials, or manual documentation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "node_id": {"type": "string", "description": "OPC UA Node ID (e.g. 'ns=2;i=10842')"},
                    },
                    "required": ["node_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_opcua_node_details",
                "description": "Read detailed OPC UA telemetry metadata including value, quality status code, and timestamps.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "node_id": {"type": "string", "description": "OPC UA Node ID"},
                    },
                    "required": ["node_id"],
                },
            },
        },
    ]
