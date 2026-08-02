"""
SAP Production Planning (PP) agent tools.

Provides on-the-fly query functions for Production Orders and
Operations via SAP OData REST APIs.

Standard SAP OData Services Used:
  - API_PRODUCTION_ORDER_2_SRV  → Production Orders & Operations
"""

import logging
from typing import Any, Dict, List, Optional

from backend.connectors.sap.client import SAPClient, escape_odata_val

logger = logging.getLogger(__name__)

# --- Standard SAP OData Service Paths ---
PRODUCTION_ORDER_SERVICE = "/sap/opu/odata/sap/API_PRODUCTION_ORDER_2_SRV"


async def get_production_orders(
    client: SAPClient,
    *,
    plant_id: Optional[str] = None,
    material_id: Optional[str] = None,
    status: Optional[str] = None,
    top: int = 50,
) -> List[Dict[str, Any]]:
    """Get active production orders from SAP.

    :param client: Connected SAPClient instance.
    :param plant_id: Filter by production plant.
    :param material_id: Filter by produced material number.
    :param status: Filter by order status.
    :param top: Maximum number of results.
    :return: List of production order records.
    """
    logger.info("PP Tool: get_production_orders(plant=%s, material=%s, top=%d)", plant_id, material_id, top)
    filters = []
    if plant_id:
        escaped_plant_id = escape_odata_val(plant_id)
        filters.append(f"ProductionPlant eq '{escaped_plant_id}'")
    if material_id:
        escaped_material_id = escape_odata_val(material_id)
        filters.append(f"Material eq '{escaped_material_id}'")

    filter_expr = " and ".join(filters) if filters else None

    result = await client.execute_odata_query(
        service_path=PRODUCTION_ORDER_SERVICE,
        entity_set="A_ProductionOrder_2",
        filter_expr=filter_expr,
        top=top,
        orderby="MfgOrderPlannedStartDate desc",
    )
    return result.get("d", {}).get("results", [])


async def get_production_order_operations(
    client: SAPClient,
    order_id: str,
    *,
    top: int = 100,
) -> List[Dict[str, Any]]:
    """Get operations/steps within a specific production order.

    :param client: Connected SAPClient instance.
    :param order_id: SAP Production Order number.
    :param top: Maximum number of operation records.
    :return: List of operation records with work center and status.
    """
    logger.info("PP Tool: get_production_order_operations(order=%s)", order_id)
    escaped_order_id = escape_odata_val(order_id)
    result = await client.execute_odata_query(
        service_path=PRODUCTION_ORDER_SERVICE,
        entity_set="A_ProductionOrderOperation_2",
        filter_expr=f"ManufacturingOrder eq '{escaped_order_id}'",
        top=top,
        orderby="OperationUnit asc",
    )
    return result.get("d", {}).get("results", [])
