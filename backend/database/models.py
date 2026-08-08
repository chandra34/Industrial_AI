"""SQLAlchemy ORM models for document metadata and ingestion job tracking."""

from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Document(Base):
    """Tracks uploaded document metadata and ownership."""

    __tablename__ = "documents"

    id = Column(String, primary_key=True, doc="UUID hex string matching the document_id used in Milvus")
    user_id = Column(String, nullable=False, index=True)
    filename = Column(String, nullable=False, doc="Original user-facing filename without the document_id prefix")
    stored_path = Column(String, nullable=False, doc="Absolute or relative path to the raw PDF on disk")
    page_count = Column(Integer, nullable=False, default=0)
    chunk_count = Column(Integer, nullable=False, default=0)
    embedded_count = Column(Integer, nullable=False, default=0)
    document_type = Column(String, nullable=True, doc="Type of document (e.g. OEM Manual, SOP, LOTO)")
    manufacturer = Column(String, nullable=True, doc="Equipment manufacturer name")
    equipment = Column(String, nullable=True, doc="Equipment name or model")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class IngestionJob(Base):
    """Tracks background ingestion job statuses."""

    __tablename__ = "ingestion_jobs"

    id = Column(String, primary_key=True, doc="UUID hex string for the job")
    user_id = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="pending", doc="pending | processing | completed | failed")
    result_json = Column(Text, nullable=True, doc="JSON-serialized UploadResponse on success")
    error = Column(Text, nullable=True, doc="Error message on failure")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class OPCUATagCatalog(Base):
    """Cached OPC UA address space tag catalog for fast agent lookups."""

    __tablename__ = "opcua_tag_catalog"

    node_id = Column(String, primary_key=True, doc="OPC UA Node ID (e.g. 'ns=2;s=Line1.Pump01.Temp')")
    browse_name = Column(String, nullable=False, index=True, doc="OPC UA browse name (e.g. 'Temperature')")
    display_name = Column(String, nullable=True, index=True, doc="Human-readable name (e.g. 'Line 1 Pump Temperature')")
    full_path = Column(String, nullable=False, index=True, doc="Full hierarchy path (e.g. 'Objects > Line_1 > Pump_01 > Temperature')")
    node_class = Column(String, nullable=False, doc="OPC UA NodeClass: 'Variable' (sensors) or 'Object' (machines/folders)")
    parent_node_id = Column(String, nullable=True, doc="Parent machine/folder node ID")
    sap_equipment_id = Column(String, nullable=True, index=True, doc="Cross-reference to SAP Equipment Master ID")
    data_type = Column(String, nullable=True, doc="OPC UA data type (e.g. 'Double', 'Boolean', 'String')")
    unit = Column(String, nullable=True, doc="Engineering unit (e.g. '°C', 'bar', 'RPM')")
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class OPCUAConnectionProfile(Base):
    """Saved OPC UA server connection profiles for dynamic machine switching."""

    __tablename__ = "opcua_connection_profiles"

    id = Column(String, primary_key=True, doc="Unique profile ID (UUID hex)")
    name = Column(String, nullable=False, doc="Human-readable profile name (e.g. 'Satake Sorter Line 1')")
    endpoint_url = Column(String, nullable=False, doc="OPC UA endpoint URL (e.g. 'opc.tcp://192.168.1.50:4840')")
    auth_mode = Column(String, nullable=False, default="anonymous", doc="'anonymous' or 'username_password'")
    username = Column(String, nullable=True, doc="OPC UA username (if auth_mode='username_password')")
    encrypted_password = Column(Text, nullable=True, doc="Fernet-encrypted password string")
    security_policy = Column(String, nullable=True, doc="Security policy string (e.g. 'Basic256Sha256,SignAndEncrypt,...')")
    is_active = Column(String, nullable=False, default="false", doc="'true' if this is the currently connected profile")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class SAPConnectionProfile(Base):
    """Saved SAP ERP connection profiles for dynamic environment switching."""

    __tablename__ = "sap_connection_profiles"

    id = Column(String, primary_key=True, doc="Unique profile ID (UUID hex)")
    name = Column(String, nullable=False, doc="Human-readable profile name (e.g. 'SAP S/4HANA Production')")
    base_url = Column(String, nullable=False, doc="SAP system base URL (e.g. 'https://my-s4hana.company.com')")
    auth_type = Column(String, nullable=False, default="basic", doc="'basic', 'oauth2', or 'apikey'")
    sap_client = Column(String, nullable=False, default="100", doc="SAP Client number (Mandant)")
    username = Column(String, nullable=True, doc="SAP username (for auth_type='basic')")
    encrypted_password = Column(Text, nullable=True, doc="Fernet-encrypted password (for auth_type='basic')")
    encrypted_api_key = Column(Text, nullable=True, doc="Fernet-encrypted API key (for auth_type='apikey')")
    client_id = Column(String, nullable=True, doc="OAuth 2.0 Client ID (for auth_type='oauth2')")
    encrypted_client_secret = Column(Text, nullable=True, doc="Fernet-encrypted OAuth client secret")
    token_url = Column(String, nullable=True, doc="OAuth 2.0 Token Endpoint URL")
    is_active = Column(String, nullable=False, default="false", doc="'true' if currently connected")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


