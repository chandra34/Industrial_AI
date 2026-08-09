"""
OPC UA connector package for Industrial AI Platform.

Provides connection management, configuration, and exception handling for OPC UA servers.
"""

from backend.connectors.opcua.connection import OPCUAClient
from backend.connectors.opcua.config import OPCUAConfig
from backend.connectors.opcua.exceptions import (
    OPCUAAuthenticationError,
    OPCUAConnectionError,
    OPCUAConnectorError,
    OPCUANotConnectedError,
    OPCUATimeoutError,
)
from backend.connectors.opcua.subscription import OPCUASubscriptionManager
from backend.connectors.opcua.utils import clean_node_id, to_json_safe

__all__ = [
    "OPCUAClient",
    "OPCUAConfig",
    "OPCUAConnectorError",
    "OPCUAConnectionError",
    "OPCUAAuthenticationError",
    "OPCUATimeoutError",
    "OPCUANotConnectedError",
    "OPCUASubscriptionManager",
    "clean_node_id",
    "to_json_safe",
]


