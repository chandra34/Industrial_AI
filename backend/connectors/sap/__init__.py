"""
SAP ERP connector package for Industrial AI Platform.

Provides connection management, configuration, and exception handling
for SAP S/4HANA and SAP ECC OData REST API integration.
"""

from backend.connectors.sap.client import SAPClient
from backend.connectors.sap.config import SAPConfig
from backend.connectors.sap.exceptions import (
    SAPAPIError,
    SAPAuthenticationError,
    SAPConnectionError,
    SAPConnectorError,
    SAPNotConnectedError,
    SAPNotFoundError,
    SAPTimeoutError,
)

__all__ = [
    "SAPClient",
    "SAPConfig",
    "SAPConnectorError",
    "SAPConnectionError",
    "SAPAuthenticationError",
    "SAPTimeoutError",
    "SAPNotConnectedError",
    "SAPAPIError",
    "SAPNotFoundError",
]
