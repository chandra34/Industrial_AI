"""
SAP Plant Maintenance (PM) agent tools.

Provides on-the-fly query functions for Equipment Master, Maintenance
Notifications, and Work Orders via SAP OData REST APIs.

Standard SAP OData Services Used:
  - API_EQUIPMENT           → Equipment Master records
  - API_MAINTNOTIFICATION   → Maintenance Notifications (breakdown reports)
  - API_MAINTENANCEORDER    → Maintenance Work Orders
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
EQUIPMENT_SERVICE = "/sap/opu/odata/sap/API_EQUIPMENT"
MAINT_NOTIFICATION_SERVICE = "/sap/opu/odata/sap/API_MAINTNOTIFICATION"
MAINT_ORDER_SERVICE = "/sap/opu/odata/sap/API_MAINTENANCEORDER"


async def get_equipment_details(
    client: SAPClient,
    equipment_id: str,
) -> Dict[str, Any]:
    """Get live details of a specific plant equipment from SAP.

    :param client: Connected SAPClient instance.
    :param equipment_id: SAP Equipment ID (e.g. '10004921').
    :return: Equipment master data dictionary.
    """
    logger.info("PM Tool: get_equipment_details(equipment_id=%s)", equipment_id)
    escaped_equipment_id = escape_odata_val(normalize_sap_id(equipment_id))
    result = await client.execute_odata_query(
        service_path=EQUIPMENT_SERVICE,
        entity_set="Equipment",
        key=f"'{escaped_equipment_id}'",
    )
    return result.get("d") or result


async def get_maintenance_notifications(
    client: SAPClient,
    *,
    plant_id: Optional[str] = None,
    equipment_id: Optional[str] = None,
    notification_type: Optional[str] = None,
    top: int = 50,
) -> List[Dict[str, Any]]:
    """Get maintenance notifications (breakdown reports) from SAP.

    :param client: Connected SAPClient instance.
    :param plant_id: Filter by maintenance plant (e.g. '1010').
    :param equipment_id: Filter by equipment ID.
    :param notification_type: Filter by notification type (e.g. 'M1' breakdown, 'M2' malfunction).
    :param top: Maximum number of results.
    :return: List of notification records.
    """
    logger.info(
        "PM Tool: get_maintenance_notifications(plant=%s, equip=%s, top=%d)",
        plant_id, equipment_id, top,
    )
    filters = []
    if plant_id:
        escaped_plant_id = escape_odata_val(plant_id)
        filters.append(f"MaintenancePlant eq '{escaped_plant_id}'")
    if equipment_id:
        escaped_equipment_id = escape_odata_val(normalize_sap_id(equipment_id))
        filters.append(f"Equipment eq '{escaped_equipment_id}'")
    if notification_type:
        escaped_notification_type = escape_odata_val(notification_type)
        filters.append(f"NotificationType eq '{escaped_notification_type}'")

    filter_expr = " and ".join(filters) if filters else None

    result = await client.execute_odata_query(
        service_path=MAINT_NOTIFICATION_SERVICE,
        entity_set="MaintenanceNotification",
        filter_expr=filter_expr,
        top=top,
        orderby="LastChangeDateTime desc",
    )
    return (result.get("d") or {}).get("results", [])


async def get_work_orders(
    client: SAPClient,
    *,
    plant_id: Optional[str] = None,
    order_type: Optional[str] = None,
    system_status: Optional[str] = None,
    top: int = 50,
) -> List[Dict[str, Any]]:
    """Get maintenance work orders from SAP.

    :param client: Connected SAPClient instance.
    :param plant_id: Filter by maintenance planning plant.
    :param order_type: Filter by order type (e.g. 'PM01' corrective, 'PM02' preventive).
    :param system_status: Filter by system status (e.g. 'REL' released, 'TECO' technically complete).
    :param top: Maximum number of results.
    :return: List of work order records.
    """
    logger.info("PM Tool: get_work_orders(plant=%s, status=%s, top=%d)", plant_id, system_status, top)
    filters = []
    if plant_id:
        escaped_plant_id = escape_odata_val(plant_id)
        filters.append(f"MaintenancePlanningPlant eq '{escaped_plant_id}'")
    if order_type:
        escaped_order_type = escape_odata_val(order_type)
        filters.append(f"MaintenanceOrderType eq '{escaped_order_type}'")
    if system_status:
        escaped_status = escape_odata_val(system_status)
        filters.append(f"substringof('{escaped_status}', ConcatenatedActiveSystStsName)")

    filter_expr = " and ".join(filters) if filters else None

    result = await client.execute_odata_query(
        service_path=MAINT_ORDER_SERVICE,
        entity_set="MaintenanceOrder",
        filter_expr=filter_expr,
        top=top,
        orderby="MaintOrdBasicStartDate desc",
    )
    return (result.get("d") or {}).get("results", [])


async def search_sap_equipment(
    client: SAPClient,
    search_text: str,
    *,
    plant_id: Optional[str] = None,
    top: int = 10,
) -> List[Dict[str, Any]]:
    """Search SAP equipment master by description text.

    Uses OData V2 substringof() filter on EquipmentName to find equipment
    matching a natural language description when no exact Equipment ID is known.

    :param client: Connected SAPClient instance.
    :param search_text: Free-text description to search (e.g. 'Boiler Feed Pump').
    :param plant_id: Optional filter by maintenance plant.
    :param top: Maximum number of results to return.
    :return: List of matching equipment records with Equipment ID and Name.
    """
    logger.info("PM Tool: search_sap_equipment(search_text='%s', plant=%s)", search_text, plant_id)
    escaped_text = escape_odata_val(search_text)
    filters = [f"substringof('{escaped_text}', EquipmentName)"]
    if plant_id:
        escaped_plant_id = escape_odata_val(plant_id)
        filters.append(f"MaintenancePlant eq '{escaped_plant_id}'")

    filter_expr = " and ".join(filters)

    result = await client.execute_odata_query(
        service_path=EQUIPMENT_SERVICE,
        entity_set="Equipment",
        filter_expr=filter_expr,
        select_fields=["Equipment", "EquipmentName", "MaintenancePlant", "EquipmentCategory"],
        top=top,
    )
    return (result.get("d") or {}).get("results", [])

