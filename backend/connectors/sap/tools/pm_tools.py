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

from backend.connectors.sap.client import SAPClient

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
    result = await client.execute_odata_query(
        service_path=EQUIPMENT_SERVICE,
        entity_set="Equipment",
        key=f"'{equipment_id}'",
    )
    return result.get("d", result)


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
        filters.append(f"MaintenancePlant eq '{plant_id}'")
    if equipment_id:
        filters.append(f"Equipment eq '{equipment_id}'")
    if notification_type:
        filters.append(f"NotificationType eq '{notification_type}'")

    filter_expr = " and ".join(filters) if filters else None

    result = await client.execute_odata_query(
        service_path=MAINT_NOTIFICATION_SERVICE,
        entity_set="MaintenanceNotification",
        filter_expr=filter_expr,
        top=top,
        orderby="LastChangeDateTime desc",
    )
    return result.get("d", {}).get("results", [])


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
        filters.append(f"MaintenancePlanningPlant eq '{plant_id}'")
    if order_type:
        filters.append(f"MaintenanceOrderType eq '{order_type}'")
    if system_status:
        filters.append(f"MaintOrdBasicStartDate ne null")

    filter_expr = " and ".join(filters) if filters else None

    result = await client.execute_odata_query(
        service_path=MAINT_ORDER_SERVICE,
        entity_set="MaintenanceOrder",
        filter_expr=filter_expr,
        top=top,
        orderby="MaintOrdBasicStartDate desc",
    )
    return result.get("d", {}).get("results", [])
