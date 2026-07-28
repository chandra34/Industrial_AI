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

__all__ = [
    "OPCUAClient",
    "OPCUAConfig",
    "OPCUAConnectorError",
    "OPCUAConnectionError",
    "OPCUAAuthenticationError",
    "OPCUATimeoutError",
    "OPCUANotConnectedError",
]
