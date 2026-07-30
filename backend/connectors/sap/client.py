"""
SAP ERP Client connection manager for the Industrial AI Platform.

Handles HTTP session lifecycle, authentication (Basic / OAuth 2.0),
CSRF token management, OData query execution, and automatic retries.
This module is strictly responsible for connection management and does
not contain business-domain tool logic.
"""

import logging
import time
from typing import Any, Dict, List, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.connectors.sap.config import SAPConfig
from backend.connectors.sap.exceptions import (
    SAPAPIError,
    SAPAuthenticationError,
    SAPConnectionError,
    SAPNotConnectedError,
    SAPNotFoundError,
    SAPTimeoutError,
)

logger = logging.getLogger(__name__)


class SAPClient:
    """Manages async HTTP connection lifecycle to an SAP ERP OData API."""

    def __init__(self, config: Optional[SAPConfig] = None) -> None:
        """Initialize the SAP Client manager.

        :param config: SAPConfig configuration object. If None, default settings are used.
        """
        self.config = config or SAPConfig()
        self._client: Optional[httpx.AsyncClient] = None
        self._oauth_token: Optional[str] = None
        self._oauth_expires_at: float = 0.0
        self._csrf_token: Optional[str] = None

    @property
    def is_connected(self) -> bool:
        """Check if the HTTP client session is active."""
        return self._client is not None and not self._client.is_closed

    async def connect(self) -> None:
        """Create the httpx.AsyncClient session with configured authentication.

        :raises SAPConnectionError: If session creation fails.
        :raises SAPAuthenticationError: If OAuth 2.0 token acquisition fails.
        """
        if self.is_connected:
            logger.info("SAP client is already connected to %s", self.config.base_url)
            return

        logger.info(
            "Initializing SAP OData connection to %s (auth=%s, timeout=%ss)",
            self.config.base_url,
            self.config.auth_type,
            self.config.timeout_seconds,
        )

        try:
            auth = None
            if self.config.auth_type == "basic":
                if not self.config.username or not self.config.password:
                    raise SAPAuthenticationError(
                        "Basic auth requires SAP_USERNAME and SAP_PASSWORD environment variables."
                    )
                auth = httpx.BasicAuth(
                    username=self.config.username,
                    password=self.config.password.get_secret_value(),
                )

            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                auth=auth,
                timeout=httpx.Timeout(self.config.timeout_seconds),
                verify=self.config.verify_ssl,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )

            # For OAuth 2.0, acquire token immediately
            if self.config.auth_type == "oauth2":
                await self._acquire_oauth_token()

            logger.info("SAP client session created for %s", self.config.base_url)

        except SAPAuthenticationError:
            raise
        except Exception as e:
            logger.error("Failed to create SAP client session: %s", e, exc_info=True)
            self._client = None
            raise SAPConnectionError(f"Failed to create SAP HTTP session: {e}") from e

    async def disconnect(self) -> None:
        """Close the httpx.AsyncClient session gracefully."""
        if self._client is None:
            logger.debug("Disconnect called, but SAP client session is None.")
            return

        logger.info("Closing SAP client session for %s...", self.config.base_url)
        try:
            await self._client.aclose()
            logger.info("SAP client session closed.")
        except Exception as e:
            logger.warning("Error closing SAP client session: %s", e)
        finally:
            self._client = None
            self._oauth_token = None
            self._csrf_token = None

    async def __aenter__(self) -> "SAPClient":
        """Async context manager entry: creates the HTTP session."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit: closes the HTTP session."""
        await self.disconnect()

    # --- OAuth 2.0 Token Management ---

    async def _acquire_oauth_token(self) -> None:
        """Acquire an OAuth 2.0 access token via Client Credentials Grant.

        :raises SAPAuthenticationError: If token acquisition fails.
        """
        if not self.config.token_url or not self.config.client_id or not self.config.client_secret:
            raise SAPAuthenticationError(
                "OAuth 2.0 requires SAP_TOKEN_URL, SAP_CLIENT_ID, and SAP_CLIENT_SECRET."
            )

        logger.info("Acquiring OAuth 2.0 token from %s", self.config.token_url)
        try:
            async with httpx.AsyncClient(verify=self.config.verify_ssl) as token_client:
                response = await token_client.post(
                    self.config.token_url,
                    data={"grant_type": "client_credentials"},
                    auth=httpx.BasicAuth(
                        self.config.client_id,
                        self.config.client_secret.get_secret_value(),
                    ),
                )
                response.raise_for_status()
                token_data = response.json()
                self._oauth_token = token_data["access_token"]
                expires_in = token_data.get("expires_in", 3600)
                # Refresh 60 seconds before actual expiry
                self._oauth_expires_at = time.time() + expires_in - 60
                logger.info("OAuth 2.0 token acquired (expires_in=%ds)", expires_in)

        except httpx.HTTPStatusError as e:
            raise SAPAuthenticationError(
                f"OAuth 2.0 token request failed: HTTP {e.response.status_code}"
            ) from e
        except Exception as e:
            raise SAPAuthenticationError(f"OAuth 2.0 token request error: {e}") from e

    async def _ensure_valid_token(self) -> None:
        """Refresh the OAuth token if expired or about to expire."""
        if self.config.auth_type != "oauth2":
            return
        if time.time() >= self._oauth_expires_at:
            logger.info("OAuth 2.0 token expired or near expiry, refreshing...")
            await self._acquire_oauth_token()

    def _build_auth_headers(self) -> Dict[str, str]:
        """Build authorization headers for the current request."""
        headers: Dict[str, str] = {}
        if self.config.auth_type == "oauth2" and self._oauth_token:
            headers["Authorization"] = f"Bearer {self._oauth_token}"
        return headers

    # --- CSRF Token (for write operations) ---

    async def fetch_csrf_token(self) -> str:
        """Fetch a CSRF token from the SAP server for write operations.

        :return: The X-CSRF-Token string.
        :raises SAPNotConnectedError: If the client is not connected.
        """
        if not self.is_connected or self._client is None:
            logger.info("SAP client session inactive. Auto-connecting for CSRF token...")
            await self.connect()

        response = await self._client.get(
            "/sap/opu/odata/sap/",
            headers={**self._build_auth_headers(), "X-CSRF-Token": "Fetch"},
            params={"sap-client": self.config.sap_client},
        )
        self._csrf_token = response.headers.get("x-csrf-token", "")
        logger.debug("CSRF token fetched: %s...", self._csrf_token[:8] if self._csrf_token else "N/A")
        return self._csrf_token

    # --- Core OData Query Execution ---

    async def execute_odata_query(
        self,
        service_path: str,
        entity_set: str,
        *,
        key: Optional[str] = None,
        filter_expr: Optional[str] = None,
        select_fields: Optional[List[str]] = None,
        top: Optional[int] = None,
        skip: Optional[int] = None,
        orderby: Optional[str] = None,
        expand: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute an OData GET query against an SAP service.

        :param service_path: OData service path (e.g. '/sap/opu/odata/sap/API_EQUIPMENT').
        :param entity_set: Entity set name (e.g. 'Equipment').
        :param key: Optional single-entity key (e.g. "'10004921'").
        :param filter_expr: OData $filter expression string.
        :param select_fields: List of field names for $select.
        :param top: Maximum number of records to return.
        :param skip: Number of records to skip (for pagination).
        :param orderby: OData $orderby expression string.
        :param expand: OData $expand expression for navigation properties.
        :return: Parsed JSON response dictionary.
        :raises SAPNotConnectedError: If client is not connected.
        :raises SAPAPIError: If the API returns a non-success status.
        """
        if not self.is_connected or self._client is None:
            logger.info("SAP client session inactive. Auto-connecting to %s...", self.config.base_url)
            await self.connect()

        await self._ensure_valid_token()

        # Build URL path
        url = f"{service_path}/{entity_set}"
        if key:
            url = f"{url}({key})"

        # Build OData query parameters
        params: Dict[str, str] = {
            "sap-client": self.config.sap_client,
            "$format": "json",
        }
        if filter_expr:
            params["$filter"] = filter_expr
        if select_fields:
            params["$select"] = ",".join(select_fields)
        if top is not None:
            params["$top"] = str(top)
        if skip is not None:
            params["$skip"] = str(skip)
        if orderby:
            params["$orderby"] = orderby
        if expand:
            params["$expand"] = expand

        logger.info("SAP OData query: GET %s | params=%s", url, params)

        return await self._execute_get_with_retry(url, params)

    @retry(
        retry=retry_if_exception_type((SAPTimeoutError, SAPConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        reraise=True,
    )
    async def _execute_get_with_retry(
        self, url: str, params: Dict[str, str]
    ) -> Dict[str, Any]:
        """Execute GET request with automatic retry for transient errors."""
        if self._client is None:
            raise SAPNotConnectedError("SAP client session is None.")

        try:
            response = await self._client.get(
                url,
                params=params,
                headers=self._build_auth_headers(),
            )
        except httpx.TimeoutException as e:
            raise SAPTimeoutError(f"SAP OData request timed out: {url}") from e
        except httpx.ConnectError as e:
            raise SAPConnectionError(f"Failed to connect to SAP: {e}") from e

        # Handle HTTP error responses
        if response.status_code == 401 or response.status_code == 403:
            raise SAPAuthenticationError(
                f"SAP authentication failed (HTTP {response.status_code}): {response.text[:200]}"
            )
        if response.status_code == 404:
            raise SAPNotFoundError(
                f"SAP resource not found: {url}",
                status_code=404,
                response_body=response.text[:500],
            )
        if response.status_code >= 400:
            raise SAPAPIError(
                f"SAP OData API error (HTTP {response.status_code}): {response.text[:200]}",
                status_code=response.status_code,
                response_body=response.text[:500],
            )

        data = response.json()
        logger.debug("SAP OData response received: %d bytes", len(response.content))
        return data
