"""
Custom exception hierarchy for the SAP ERP connector.

Provides meaningful domain-specific exceptions wrapping raw HTTP/OData errors.
"""


class SAPConnectorError(Exception):
    """Base exception for all SAP connector errors."""

    pass


class SAPConnectionError(SAPConnectorError):
    """Raised when establishing or maintaining an SAP HTTP connection fails."""

    pass


class SAPAuthenticationError(SAPConnectorError):
    """Raised when SAP authentication (Basic or OAuth 2.0) fails."""

    pass


class SAPTimeoutError(SAPConnectionError):
    """Raised when an SAP OData request or connection times out."""

    pass


class SAPNotConnectedError(SAPConnectorError):
    """Raised when an operation is attempted while the SAP client is not connected."""

    pass


class SAPAPIError(SAPConnectorError):
    """Raised when SAP OData API returns a non-success HTTP status (4xx/5xx)."""

    def __init__(self, message: str, status_code: int = 0, response_body: str = ""):
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(message)


class SAPNotFoundError(SAPAPIError):
    """Raised when the requested SAP resource is not found (HTTP 404)."""

    pass
