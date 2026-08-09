"""
SAP Material Management (MM) agent tools.

Provides on-the-fly query functions for Material Master, Stock Levels,
and Bill of Materials via SAP OData REST APIs.

Standard SAP OData Services Used:
  - API_PRODUCT_SRV             → Material Master records
  - API_MATERIAL_STOCK_SRV      → Real-time stock/inventory levels
  - API_BILL_OF_MATERIAL_SRV    → Bill of Materials (BOM) structure
"""

import logging
from typing import Any, Dict, List, Optional

from backend.connectors.sap.client import (
    SAPClient,
    escape_odata_val,
    normalize_sap_id,
)

logger = logging.getLogger(__name__)

# --- Standard SAP OData Service Paths ---
PRODUCT_SERVICE = "/sap/opu/odata/sap/API_PRODUCT_SRV"
MATERIAL_STOCK_SERVICE = "/sap/opu/odata/sap/API_MATERIAL_STOCK_SRV"
BOM_SERVICE = "/sap/opu/odata/sap/API_BILL_OF_MATERIAL_SRV"


async def get_material_master(
    client: SAPClient,
    material_id: str,
) -> Dict[str, Any]:
    """Get material master data (specs, description, weight, dimensions).

    :param client: Connected SAPClient instance.
    :param material_id: SAP Material Number (e.g. 'MAT-001').
    :return: Material master data dictionary.
    """
    logger.info("MM Tool: get_material_master(material_id=%s)", material_id)
    escaped_material_id = escape_odata_val(normalize_sap_id(material_id))
    result = await client.execute_odata_query(
        service_path=PRODUCT_SERVICE,
        entity_set="A_Product",
        key=f"'{escaped_material_id}'",
    )
    return result.get("d") or result


async def check_material_stock(
    client: SAPClient,
    material_id: str,
    plant_id: str,
) -> List[Dict[str, Any]]:
    """Check real-time inventory stock level for a material in a plant.

    :param client: Connected SAPClient instance.
    :param material_id: SAP Material Number.
    :param plant_id: SAP Plant ID (e.g. '1010').
    :return: List of stock position records.
    """
    logger.info("MM Tool: check_material_stock(material=%s, plant=%s)", material_id, plant_id)
    escaped_material_id = escape_odata_val(normalize_sap_id(material_id))
    escaped_plant_id = escape_odata_val(plant_id)
    result = await client.execute_odata_query(
        service_path=MATERIAL_STOCK_SERVICE,
        entity_set="A_MatlStkInAcctMod",
        filter_expr=f"Material eq '{escaped_material_id}' and Plant eq '{escaped_plant_id}'",
    )
    return (result.get("d") or {}).get("results", [])


async def get_bill_of_materials(
    client: SAPClient,
    material_id: str,
    plant_id: str,
    *,
    top: int = 100,
) -> List[Dict[str, Any]]:
    """Get Bill of Materials (BOM) component breakdown for a material.

    :param client: Connected SAPClient instance.
    :param material_id: Parent material number.
    :param plant_id: SAP Plant ID.
    :param top: Maximum number of BOM items to return.
    :return: List of BOM item records.
    """
    logger.info("MM Tool: get_bill_of_materials(material=%s, plant=%s)", material_id, plant_id)
    escaped_material_id = escape_odata_val(normalize_sap_id(material_id))
    escaped_plant_id = escape_odata_val(plant_id)
    result = await client.execute_odata_query(
        service_path=BOM_SERVICE,
        entity_set="MaterialBOMItem",
        filter_expr=f"Material eq '{escaped_material_id}' and Plant eq '{escaped_plant_id}'",
        top=top,
    )
    return (result.get("d") or {}).get("results", [])


async def search_sap_materials(
    client: SAPClient,
    search_text: str,
    *,
    language: str = "EN",
    top: int = 10,
) -> List[Dict[str, Any]]:
    """Search SAP material master by description text.

    Uses OData V2 substringof() filter on ProductDescription to find materials
    matching a natural language description when no exact Material Number is known.

    :param client: Connected SAPClient instance.
    :param search_text: Free-text description to search (e.g. 'agitator motor bearing').
    :param language: Language key code to filter records (default 'EN').
    :param top: Maximum number of results to return.
    :return: List of matching material records with Product ID and Description.
    """
    logger.info("MM Tool: search_sap_materials(search_text='%s', language='%s')", search_text, language)
    escaped_text = escape_odata_val(search_text)
    escaped_lang = escape_odata_val(language)
    filter_expr = f"substringof('{escaped_text}', ProductDescription) and Language eq '{escaped_lang}'"

    result = await client.execute_odata_query(
        service_path=PRODUCT_SERVICE,
        entity_set="A_ProductDescription",
        filter_expr=filter_expr,
        select_fields=["Product", "ProductDescription", "Language"],
        top=top,
    )
    return (result.get("d") or {}).get("results", [])

