"""
SAP Quality Management (QM) agent tools.

Provides on-the-fly query functions for Inspection Lots and
Quality Notifications via SAP OData REST APIs.

Standard SAP OData Services Used:
  - API_INSPECTIONLOT_SRV           → Inspection Lots (lab test results)
  - API_QUALITYNOTIFICATION_SRV     → Quality Notifications (defect reports)
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
INSPECTION_LOT_SERVICE = "/sap/opu/odata/sap/API_INSPECTIONLOT_SRV"
QUALITY_NOTIFICATION_SERVICE = "/sap/opu/odata/sap/API_QUALITYNOTIFICATION_SRV"


async def get_inspection_lots(
    client: SAPClient,
    *,
    material_id: Optional[str] = None,
    batch_id: Optional[str] = None,
    plant_id: Optional[str] = None,
    top: int = 50,
) -> List[Dict[str, Any]]:
    """Get inspection lots (lab test results, pass/fail status).

    :param client: Connected SAPClient instance.
    :param material_id: Filter by material number.
    :param batch_id: Filter by batch number.
    :param plant_id: Filter by plant.
    :param top: Maximum number of results.
    :return: List of inspection lot records.
    """
    logger.info("QM Tool: get_inspection_lots(material=%s, batch=%s, plant=%s)", material_id, batch_id, plant_id)
    filters = []
    if material_id:
        escaped_material_id = escape_odata_val(normalize_sap_id(material_id))
        filters.append(f"Material eq '{escaped_material_id}'")
    if batch_id:
        escaped_batch_id = escape_odata_val(batch_id)
        filters.append(f"Batch eq '{escaped_batch_id}'")
    if plant_id:
        escaped_plant_id = escape_odata_val(plant_id)
        filters.append(f"Plant eq '{escaped_plant_id}'")

    filter_expr = " and ".join(filters) if filters else None

    result = await client.execute_odata_query(
        service_path=INSPECTION_LOT_SERVICE,
        entity_set="A_InspectionLot",
        filter_expr=filter_expr,
        top=top,
    )
    return (result.get("d") or {}).get("results", [])


async def get_quality_notifications(
    client: SAPClient,
    *,
    plant_id: Optional[str] = None,
    notification_type: Optional[str] = None,
    top: int = 50,
) -> List[Dict[str, Any]]:
    """Get quality notifications (defect reports, root cause records).

    :param client: Connected SAPClient instance.
    :param plant_id: Filter by plant.
    :param notification_type: Filter by notification type (e.g. 'Q1' quality, 'Q2' complaint).
    :param top: Maximum number of results.
    :return: List of quality notification records.
    """
    logger.info("QM Tool: get_quality_notifications(plant=%s, type=%s, top=%d)", plant_id, notification_type, top)
    filters = []
    if plant_id:
        escaped_plant_id = escape_odata_val(plant_id)
        filters.append(f"Plant eq '{escaped_plant_id}'")
    if notification_type:
        escaped_notification_type = escape_odata_val(notification_type)
        filters.append(f"NotificationType eq '{escaped_notification_type}'")

    filter_expr = " and ".join(filters) if filters else None

    result = await client.execute_odata_query(
        service_path=QUALITY_NOTIFICATION_SERVICE,
        entity_set="QualityNotification",
        filter_expr=filter_expr,
        top=top,
    )
    return (result.get("d") or {}).get("results", [])
