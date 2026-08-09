"""
SAP ERP universal agent tools package.

Exports all industry-agnostic tool functions and a tool registry
for LLM agent function-calling / tool-binding integration.
"""

from backend.connectors.sap.tools.pm_tools import (
    get_equipment_details,
    get_maintenance_notifications,
    get_work_orders,
    search_sap_equipment,
)
from backend.connectors.sap.tools.mm_tools import (
    check_material_stock,
    get_bill_of_materials,
    get_material_master,
    search_sap_materials,
)
from backend.connectors.sap.tools.pp_tools import (
    get_production_order_operations,
    get_production_orders,
)
from backend.connectors.sap.tools.qm_tools import (
    get_inspection_lots,
    get_quality_notifications,
)

# Registry of all SAP tools for agent binding
ALL_SAP_TOOLS = {
    # Plant Maintenance (PM)
    "get_equipment_details": get_equipment_details,
    "get_maintenance_notifications": get_maintenance_notifications,
    "get_work_orders": get_work_orders,
    "search_sap_equipment": search_sap_equipment,
    # Material Management (MM)
    "get_material_master": get_material_master,
    "check_material_stock": check_material_stock,
    "get_bill_of_materials": get_bill_of_materials,
    "search_sap_materials": search_sap_materials,
    # Production Planning (PP)
    "get_production_orders": get_production_orders,
    "get_production_order_operations": get_production_order_operations,
    # Quality Management (QM)
    "get_inspection_lots": get_inspection_lots,
    "get_quality_notifications": get_quality_notifications,
}

__all__ = [
    "ALL_SAP_TOOLS",
    "get_equipment_details",
    "get_maintenance_notifications",
    "get_work_orders",
    "search_sap_equipment",
    "get_material_master",
    "check_material_stock",
    "get_bill_of_materials",
    "search_sap_materials",
    "get_production_orders",
    "get_production_order_operations",
    "get_inspection_lots",
    "get_quality_notifications",
]

