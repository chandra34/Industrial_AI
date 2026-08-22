"""
OPC UA Client connection manager for the Industrial AI Platform.

Handles connection lifecycle, authentication, state monitoring, automatic
reconnection (via asyncua built-in supervisor), and structured logging.
This module is strictly responsible for connection management and does not
contain node browsing, reading, or business logic.
"""

import asyncio
import logging
from typing import Optional, Any, Dict

from backend.connectors.opcua.config import OPCUAConfig
from backend.connectors.opcua.exceptions import (
    OPCUAAuthenticationError,
    OPCUAConnectionError,
    OPCUANotConnectedError,
    OPCUATimeoutError,
)

logger = logging.getLogger(__name__)


class OPCUAClient:
    """Manages connection lifecycle to an OPC UA server."""

    def __init__(self, config: Optional[OPCUAConfig] = None) -> None:
        """Initialize the OPC UA Client manager.

        :param config: OPCUAConfig configuration object. If None, default settings are used.
        """
        self.config = config or OPCUAConfig()
        self._client: Optional[Any] = None
        self._capabilities: Dict[str, Any] = {}

    @property
    def raw_client(self) -> Any:
        """Expose the underlying asyncua.Client instance.

        :return: Connected asyncua.Client instance.
        :raises OPCUANotConnectedError: If the client is not connected.
        """
        if not self.is_connected or self._client is None:
            raise OPCUANotConnectedError(
                "Client is not connected to an OPC UA server. Call connect() first."
            )
        return self._client

    @property
    def is_connected(self) -> bool:
        """Check if the OPC UA client is connected.

        :return: True if connected, False otherwise.
        """
        if self._client is None:
            return False

        try:
            from asyncua.client.ua_client import UaClientState
            return self._client.state == UaClientState.CONNECTED
        except Exception:
            return False

    @property
    def state(self) -> Any:
        """Get the current connection state.

        :return: UaClientState if client exists, otherwise 'DISCONNECTED'.
        """
        if self._client is None:
            try:
                from asyncua.client.ua_client import UaClientState
                return UaClientState.DISCONNECTED
            except ImportError:
                return "DISCONNECTED"
        return self._client.state

    async def connect(self) -> None:
        """Establish connection to the OPC UA server with configured settings.

        :raises OPCUAConnectionError: If network or connection setup fails.
        :raises OPCUAAuthenticationError: If authentication credentials fail.
        :raises OPCUATimeoutError: If connection times out.
        """
        if self.is_connected:
            logger.info("OPC UA client is already connected to %s", self.config.endpoint_url)
            return

        try:
            from asyncua import Client
            from asyncua.ua.uaerrors._base import UaError
        except ImportError as e:
            logger.error("asyncua library is not installed: %s", e)
            raise OPCUAConnectionError(
                "The 'asyncua' package is required to connect to OPC UA servers. "
                "Please install it using 'pip install asyncua'."
            ) from e

        logger.info(
            "Initializing OPC UA connection to %s (auto_reconnect=%s, timeout=%ss)",
            self.config.endpoint_url,
            self.config.auto_reconnect,
            self.config.timeout_seconds,
        )

        try:
            self._client = Client(
                url=self.config.endpoint_url,
                timeout=self.config.timeout_seconds,
                watchdog_intervall=self.config.watchdog_interval,
                auto_reconnect=self.config.auto_reconnect,
                reconnect_max_delay=self.config.reconnect_max_delay,
                reconnect_request_timeout=self.config.reconnect_request_timeout,
            )

            # Set session name and session timeout if configured
            if self.config.session_name:
                self._client.name = self.config.session_name
            if hasattr(self.config, "session_timeout_ms") and self.config.session_timeout_ms:
                self._client.session_timeout = self.config.session_timeout_ms

            # Configure Authentication (Username/Password or Anonymous)
            if self.config.username is not None and self.config.password is not None:
                logger.info("Configuring Username/Password authentication for user: %s", self.config.username)
                self._client.set_user(self.config.username)
                self._client.set_password(self.config.password.get_secret_value())
            else:
                logger.info("Configuring Anonymous authentication")

            # Configure Security String if provided
            if self.config.security_string:
                logger.info("Applying security configuration: %s", self.config.security_string)
                await self._client.set_security_string(self.config.security_string)

            logger.info("Connecting to OPC UA server...")
            await self._client.connect()
            logger.info("Successfully connected to OPC UA server at %s", self.config.endpoint_url)

        except asyncio.TimeoutError as e:
            logger.error("Timeout connecting to OPC UA server at %s: %s", self.config.endpoint_url, e)
            self._client = None
            raise OPCUATimeoutError(f"Connection to {self.config.endpoint_url} timed out.") from e

        except ConnectionRefusedError as e:
            logger.error("Connection refused by OPC UA server at %s: %s", self.config.endpoint_url, e)
            self._client = None
            raise OPCUAConnectionError(f"Connection refused by {self.config.endpoint_url}.") from e

        except UaError as e:
            error_msg = str(e)
            logger.error("OPC UA protocol error during connect to %s: %s", self.config.endpoint_url, error_msg)
            self._client = None
            if "BadUserAccessDenied" in error_msg or "BadIdentityToken" in error_msg:
                raise OPCUAAuthenticationError(f"Authentication failed for {self.config.endpoint_url}: {error_msg}") from e
            raise OPCUAConnectionError(f"OPC UA protocol error connecting to {self.config.endpoint_url}: {error_msg}") from e

        except Exception as e:
            logger.error("Unexpected error connecting to OPC UA server at %s: %s", self.config.endpoint_url, e, exc_info=True)
            self._client = None
            raise OPCUAConnectionError(f"Unexpected connection error: {e}") from e

    async def disconnect(self) -> None:
        """Disconnect gracefully from the OPC UA server."""
        if self._client is None:
            logger.debug("Disconnect called, but client instance is None.")
            return

        logger.info("Disconnecting from OPC UA server at %s...", self.config.endpoint_url)
        try:
            await self._client.disconnect()
            logger.info("Successfully disconnected from OPC UA server.")
        except Exception as e:
            logger.warning("Error occurred during OPC UA disconnect: %s", e)
        finally:
            self._client = None
            self._capabilities = {}

    async def __aenter__(self) -> "OPCUAClient":
        """Async context manager entry: connects to the OPC UA server."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit: disconnects gracefully."""
        await self.disconnect()

    async def get_server_capabilities(self) -> Dict[str, Any]:
        """Fetch and cache server capabilities from the OPC UA Server.

        :return: Dictionary containing server capabilities and profile flags.
        :raises OPCUANotConnectedError: If the client is not connected.
        """
        if not self.is_connected:
            raise OPCUANotConnectedError("Client is not connected. Connect first to fetch capabilities.")

        if self._capabilities:
            return self._capabilities

        from asyncua import ua
        capabilities = {
            "max_nodes_per_read": 1000,
            "min_supported_sample_rate_ms": 100.0,
            "server_profiles": [],
            "supports_history": False,
            "supports_events": False,
        }

        try:
            # 1. Fetch ServerProfileArray (ns=0;i=2269)
            try:
                profile_node = self._client.get_node("ns=0;i=2269")
                profiles = await profile_node.read_value()
                if isinstance(profiles, list):
                    capabilities["server_profiles"] = [str(p) for p in profiles]
            except Exception as e:
                logger.debug("Failed to read ServerProfileArray: %s", e)

            # 2. Fetch MinSupportedSampleRate (ns=0;i=2272)
            try:
                sample_rate_node = self._client.get_node("ns=0;i=2272")
                rate = await sample_rate_node.read_value()
                if rate is not None:
                    capabilities["min_supported_sample_rate_ms"] = float(rate)
            except Exception as e:
                logger.debug("Failed to read MinSupportedSampleRate: %s", e)

            # 3. Detect supports_history and supports_events from server_profiles
            profiles_str = "".join(capabilities["server_profiles"]).lower()
            if any(term in profiles_str for term in ["historicaldataaccess", "history", "hda", "historicalrawdata"]):
                capabilities["supports_history"] = True
            if any(term in profiles_str for term in ["alarms", "events", "ac", "alarmscondition"]):
                capabilities["supports_events"] = True

            # Heuristics: if profile array is empty, default both to True to allow query attempts
            if not capabilities["server_profiles"]:
                capabilities["supports_history"] = True
                capabilities["supports_events"] = True

            # 4. Check OperationLimits (ns=0;i=11704) for MaxNodesPerRead (ns=0;i=11705)
            try:
                max_read_node = self._client.get_node("ns=0;i=11705")
                max_read = await max_read_node.read_value()
                if max_read is not None:
                    capabilities["max_nodes_per_read"] = int(max_read)
            except Exception as e:
                logger.debug("Failed to read MaxNodesPerRead operation limit: %s", e)

        except Exception as e:
            logger.warning("Error fetching server capabilities: %s. Using default capabilities.", e)

        self._capabilities = capabilities
        return self._capabilities

    @property
    def supports_history(self) -> bool:
        """Return True if the connected server supports historical data access."""
        return self._capabilities.get("supports_history", False)

    @property
    def supports_events(self) -> bool:
        """Return True if the connected server supports alarms and events."""
        return self._capabilities.get("supports_events", False)
