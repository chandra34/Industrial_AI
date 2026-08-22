"""
OPC UA connection configuration settings using Pydantic v2.
"""

from typing import Optional
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class OPCUAConfig(BaseSettings):
    """Configuration model for connecting to an OPC UA server."""

    model_config = SettingsConfigDict(
        env_prefix="OPCUA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    endpoint_url: str = Field(
        default="opc.tcp://localhost:4840",
        description="OPC UA Server Endpoint URL",
    )
    timeout_seconds: float = Field(
        default=20.0,
        gt=0.0,
        description="Request and connection timeout in seconds",
    )
    username: Optional[str] = Field(
        default=None,
        description="Username for authentication if required",
    )
    password: Optional[SecretStr] = Field(
        default=None,
        description="Password for authentication if required",
    )
    security_string: Optional[str] = Field(
        default=None,
        description=(
            "Security mode string format: 'Policy,Mode,certificate,private_key[,server_certificate]'. "
            "Example: 'Basic256Sha256,SignAndEncrypt,cert.pem,key.pem'"
        ),
    )
    auto_reconnect: bool = Field(
        default=True,
        description="Enable automatic reconnection on transport loss via asyncua supervisor task",
    )
    reconnect_max_delay: float = Field(
        default=30.0,
        gt=0.0,
        description="Exponential backoff cap for reconnection attempts in seconds",
    )
    reconnect_request_timeout: float = Field(
        default=60.0,
        gt=0.0,
        description="How long requests block waiting for connection to become ready while reconnecting",
    )
    watchdog_interval: float = Field(
        default=20.0,
        gt=0.0,
        description="Server alive watchdog check interval in seconds",
    )
    session_timeout_ms: int = Field(
        default=60000,
        gt=0,
        description="OPC UA session timeout requested from the server in milliseconds",
    )
    session_name: str = Field(
        default="IndustrialAI_OPCUA_Client",
        description="Session display name on OPC UA server",
    )
    min_catalog_match_score: int = Field(
        default=2,
        ge=1,
        description="Minimum matching keyword count threshold for Tier 2 relaxed OR tag catalog search",
    )
