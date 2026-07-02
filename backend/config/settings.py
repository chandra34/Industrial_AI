from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables and ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="RAG Milvus App", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_file: str | None = Field(default="backend/logs/app.log", alias="LOG_FILE")
    log_rotation_mb: int = Field(default=10, alias="LOG_ROTATION_MB")
    log_backup_count: int = Field(default=5, alias="LOG_BACKUP_COUNT")

    project_root: Path = Path(__file__).resolve().parents[2]
    upload_dir: Path = Path("backend/uploads")
    max_upload_mb: int = Field(default=15, alias="MAX_UPLOAD_MB")

    milvus_host: str = Field(default="localhost", alias="MILVUS_HOST")
    milvus_port: int = Field(default=19530, alias="MILVUS_PORT")
    milvus_uri: str | None = Field(default="./milvus_local.db", alias="MILVUS_URI")
    milvus_token: str | None = Field(default=None, alias="MILVUS_TOKEN")
    milvus_collection_name: str = Field(default="rag_documents", alias="MILVUS_COLLECTION_NAME")
    milvus_alias: str = Field(default="default", alias="MILVUS_ALIAS")
    milvus_dimension: int = Field(default=1536, alias="MILVUS_DIMENSION")
    milvus_index_type: str = Field(default="FLAT", alias="MILVUS_INDEX_TYPE")
    milvus_metric_type: str = Field(default="IP", alias="MILVUS_METRIC_TYPE")
    milvus_m: int = Field(default=16, alias="MILVUS_M")
    milvus_ef_construction: int = Field(default=200, alias="MILVUS_EF_CONSTRUCTION")
    milvus_ef_search: int = Field(default=64, alias="MILVUS_EF_SEARCH")
    milvus_nlist: int = Field(default=128, alias="MILVUS_NLIST")
    milvus_nprobe: int = Field(default=16, alias="MILVUS_NPROBE")
    milvus_insert_batch_size: int = Field(default=250, alias="MILVUS_INSERT_BATCH_SIZE")

    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    voyage_api_key: str = Field(default="", alias="VOYAGE_API_KEY")
    embedding_provider: str = Field(default="gemini", alias="EMBEDDING_PROVIDER")
    embedding_model_name: str = Field(default="gemini-embedding-2", alias="EMBEDDING_MODEL_NAME")
    embedding_batch_size: int = Field(default=32, alias="EMBEDDING_BATCH_SIZE")
    embedding_concurrency: int = Field(default=5, alias="EMBEDDING_CONCURRENCY")
    document_parser: str = Field(default="pymupdf", alias="DOCUMENT_PARSER")
    chunk_size: int = Field(default=1000, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=150, alias="CHUNK_OVERLAP")
    top_k: int = Field(default=5, alias="TOP_K")
    max_context_chars: int = Field(default=12000, alias="MAX_CONTEXT_CHARS")
    firebase_credentials_path: str | None = Field(default=None, alias="FIREBASE_CREDENTIALS_PATH")
    firebase_credentials_json: str | None = Field(default=None, alias="FIREBASE_CREDENTIALS_JSON")
    

    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    llm_provider: str = Field(default="groq", alias="LLM_PROVIDER")
    llm_model: str = Field(default="llama-3.1-8b-instant", alias="LLM_MODEL")
    llm_temperature: float = Field(default=0.2, alias="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=1024, alias="LLM_MAX_TOKENS")

    # BM25 sparse search settings (uses Milvus native BM25 via sparse vectors)
    bm25_enabled: bool = Field(default=True, alias="BM25_ENABLED")

    # Reranker Settings
    reranker_enabled: bool = Field(default=True, alias="RERANKER_ENABLED")
    reranker_model_name: str = Field(default="BAAI/bge-reranker-v2-m3", alias="RERANKER_MODEL_NAME")
    hf_token: str = Field(default="", alias="HF_TOKEN")
    reranker_candidate_k: int = Field(default=25, alias="RERANKER_CANDIDATE_K")

    @property
    def resolved_milvus_uri(self) -> str:
        """Absolute Milvus URI: .db file for Lite, or http(s) for a remote server."""
        raw = (self.milvus_uri or "").strip()
        if raw:
            if raw.lower().endswith(".db"):
                path = Path(raw)
                if not path.is_absolute():
                    path = self.project_root / path
                return str(path.resolve())
            return raw
        return f"http://{self.milvus_host}:{self.milvus_port}"

    @property
    def uses_milvus_lite(self) -> bool:
        """Return True when Milvus is configured to use a local ``.db`` file."""
        return self.resolved_milvus_uri.lower().endswith(".db")

    @property
    def resolved_upload_dir(self) -> Path:
        """Return the absolute path to the PDF upload directory."""
        upload_path = self.upload_dir
        if not upload_path.is_absolute():
            upload_path = self.project_root / upload_path
        return upload_path



@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance."""
    return Settings()
