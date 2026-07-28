"""
Custom exception hierarchy for the OPC UA connector.

Provides meaningful domain-specific exceptions wrapping raw asyncua errors.
"""


class OPCUAConnectorError(Exception):
    """Base exception for all OPC UA connector errors."""

    pass


class OPCUAConnectionError(OPCUAConnectorError):
    """Raised when establishing or maintaining an OPC UA connection fails."""

    pass


class OPCUAAuthenticationError(OPCUAConnectorError):
    """Raised when authentication credentials or security policy check fails."""

    pass


class OPCUATimeoutError(OPCUAConnectionError):
    """Raised when an OPC UA connection or request operation times out."""

    pass


class OPCUANotConnectedError(OPCUAConnectorError):
    """Raised when an operation is attempted while the OPC UA client is not connected."""

    pass
