"""
SAP ERP connection configuration settings using Pydantic v2.

Supports both Basic Authentication and OAuth 2.0 Client Credentials
for SAP S/4HANA (Cloud & On-Premise) and SAP ECC via SAP Gateway.
"""

from typing import Optional, Literal
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class SAPConfig(BaseSettings):
    """Configuration model for connecting to an SAP ERP OData API."""

    model_config = SettingsConfigDict(
        env_prefix="SAP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Connection ---
    base_url: str = Field(
        default="https://my-sap-system.example.com",
        description=(
            "SAP system base URL (e.g. 'https://my-s4hana.company.com'). "
            "OData service paths are appended to this."
        ),
    )
    timeout_seconds: float = Field(
        default=30.0,
        gt=0.0,
        description="HTTP request timeout in seconds.",
    )

    # --- Authentication ---
    auth_type: Literal["basic", "oauth2", "apikey"] = Field(
        default="basic",
        description="Authentication method: 'basic', 'oauth2', or 'apikey' (for SAP Business Accelerator Hub Sandbox).",
    )
    api_key: Optional[SecretStr] = Field(
        default=None,
        description="API Key for SAP Business Accelerator Hub Sandbox (when auth_type='apikey').",
    )
    username: Optional[str] = Field(
        default=None,
        description="SAP service user for Basic Authentication.",
    )
    password: Optional[SecretStr] = Field(
        default=None,
        description="SAP service user password for Basic Authentication.",
    )
    client_id: Optional[str] = Field(
        default=None,
        description="OAuth 2.0 Client ID (for SAP BTP / S/4HANA Cloud).",
    )
    client_secret: Optional[SecretStr] = Field(
        default=None,
        description="OAuth 2.0 Client Secret.",
    )
    token_url: Optional[str] = Field(
        default=None,
        description="OAuth 2.0 Token Endpoint URL (e.g. 'https://<subdomain>.authentication.eu10.hana.ondemand.com/oauth/token').",
    )

    # --- SAP Client Number ---
    sap_client: str = Field(
        default="100",
        description="SAP Client number (Mandant). Sent as 'sap-client' query parameter.",
    )

    # --- Retry & Resilience ---
    max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum retry attempts for transient failures (5xx, timeouts).",
    )
    retry_backoff_base: float = Field(
        default=1.0,
        gt=0.0,
        description="Base delay in seconds for exponential backoff between retries.",
    )

    # --- SSL ---
    verify_ssl: bool = Field(
        default=True,
        description="Whether to verify SSL certificates. Set False only for dev/sandbox.",
    )
