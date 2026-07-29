import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import time
import uuid
import firebase_admin
from firebase_admin import credentials

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router as api_router
from backend.config.settings import get_settings
from backend.rag.embeddings import EmbeddingFactory
from backend.rag.llm import LLMFactory
from backend.rag.pipeline import RAGPipeline
from backend.rag.retrieval import RetrievalService
from backend.services.ingest_service import IngestService
from backend.services.reranker_service import RerankerService
from backend.services.document_service import DocumentService
from backend.services.job_status_service import JobStatusService
from backend.services.storage import create_storage_provider
from backend.vectordb.milvus_db import MilvusStore
from backend.utils.logging_context import CorrelationFilter, request_id_var, route_var, clear_context
from backend.connectors.sap import SAPClient, SAPConfig
from backend.agents.orchestrator import IndustrialOrchestrator


settings = get_settings()

# Configure unified standard logging format
log_format = "%(asctime)s | %(levelname)s | [%(request_id)s] [%(user_id)s] [%(document_id)s] | %(name)s | %(message)s"
handlers = []

# Console handler
console_handler = logging.StreamHandler()
console_handler.addFilter(CorrelationFilter())
console_handler.setFormatter(logging.Formatter(log_format))
handlers.append(console_handler)

# File handler with rotation (if log_file path is configured)
if settings.log_file:
    log_path = Path(settings.log_file)
    if not log_path.is_absolute():
        log_path = settings.project_root / log_path
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            filename=log_path,
            maxBytes=settings.log_rotation_mb * 1024 * 1024,
            backupCount=settings.log_backup_count,
            encoding="utf-8",
        )
        file_handler.addFilter(CorrelationFilter())
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)
    except Exception as e:
        print(f"Failed to initialize rotating file log handler at {log_path}: {e}")

# Apply configuration to the root logger
root_logger = logging.getLogger()
root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
root_logger.handlers = handlers

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name, version="1.0.0")

@app.middleware("http")
async def correlation_logging_middleware(request: Request, call_next):
    """Middleware to manage async logging contexts, generate correlation IDs, and track request timing."""
    clear_context()
    
    # Extract request-id from headers or generate new one
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request_id_var.set(request_id)
    route_var.set(f"{request.method} {request.url.path}")
    
    start_time = time.perf_counter()
    logger.info("Request started: %s %s", request.method, request.url.path)
    
    try:
        response = await call_next(request)
        duration = time.perf_counter() - start_time
        logger.info(
            "Request completed: %s %s | status: %d | duration: %.3fs",
            request.method,
            request.url.path,
            response.status_code,
            duration,
        )
        # Expose correlation ID to client response headers
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception as exc:
        duration = time.perf_counter() - start_time
        logger.error(
            "Request failed: %s %s | duration: %.3fs | error: %s",
            request.method,
            request.url.path,
            duration,
            str(exc),
            exc_info=True,
        )
        raise

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)



def retry_initialization(func, description: str, retries: int = 5, delay: float = 2.0):
    """Retry a startup connection or initialization function with exponential backoff."""
    current_delay = delay
    for attempt in range(1, retries + 1):
        try:
            return func()
        except Exception as exc:
            if attempt == retries:
                logger.error(
                    "Startup critical initialization failed for %s after %d attempts: %s. Halting.",
                    description,
                    attempt,
                    exc,
                )
                raise
            logger.warning(
                "Failed to initialize %s (attempt %d/%d). Error: %s. Retrying in %.1f seconds...",
                description,
                attempt,
                retries,
                exc,
                current_delay,
            )
            time.sleep(current_delay)
            current_delay *= 2


async def retry_initialization_async(func, description: str, retries: int = 5, delay: float = 2.0):
    """Retry an async startup connection or initialization function with exponential backoff."""
    import asyncio
    current_delay = delay
    for attempt in range(1, retries + 1):
        try:
            return await func()
        except Exception as exc:
            if attempt == retries:
                logger.error(
                    "Startup critical initialization failed for %s after %d attempts: %s. Halting.",
                    description,
                    attempt,
                    exc,
                )
                raise
            logger.warning(
                "Failed to initialize %s (attempt %d/%d). Error: %s. Retrying in %.1f seconds...",
                description,
                attempt,
                retries,
                exc,
                current_delay,
            )
            await asyncio.sleep(current_delay)
            current_delay *= 2


@app.on_event("startup")
async def on_startup() -> None:
    """Initialize Firebase, services, and attach them to application state."""
    if settings.hf_token:
        os.environ["HF_TOKEN"] = settings.hf_token
    settings.resolved_upload_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Starting %s", settings.app_name)

    # Initialize metadata database tables
    from backend.database.session import engine
    from backend.database.models import Base
    
    async def init_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
    await retry_initialization_async(init_db, "Metadata database tables")
    logger.info("Metadata database tables initialized")

    # Initialize Firebase Admin SDK
    if not firebase_admin._apps:
        try:
            if settings.firebase_credentials_json:
                try:
                    cred_dict = json.loads(settings.firebase_credentials_json)
                    cred = credentials.Certificate(cred_dict)
                    firebase_admin.initialize_app(cred)
                    logger.info("Firebase Admin SDK initialized using JSON string from environment")
                except Exception as json_exc:
                    logger.error("Failed to parse FIREBASE_CREDENTIALS_JSON: %s", json_exc)
                    raise json_exc
            elif settings.firebase_credentials_path:
                cred = credentials.Certificate(settings.firebase_credentials_path)
                firebase_admin.initialize_app(cred)
                logger.info("Firebase Admin SDK initialized using certificate: %s", settings.firebase_credentials_path)
            else:
                firebase_admin.initialize_app()
                logger.info("Firebase Admin SDK initialized using default credentials")
        except Exception as exc:
            logger.warning("Could not initialize Firebase Admin SDK: %s. Authentication might fail.", exc)


    embedding_service = EmbeddingFactory.create(settings)
    
    def init_milvus():
        return MilvusStore(settings)
        
    vector_store = retry_initialization(init_milvus, "Milvus Store")
    llm_service = LLMFactory.create(settings)

    # Initialize storage provider (local / s3 / gcs)
    storage_provider = create_storage_provider(settings)
    logger.info("Storage provider initialized: %s", settings.storage_provider)

    # BM25 sparse search is handled natively by Milvus (schema + SPARSE_INVERTED_INDEX)
    if settings.bm25_enabled:
        logger.info("BM25 sparse search enabled (Milvus native)")
    else:
        logger.info("BM25 sparse search disabled")

    # Reranker service
    reranker_service: RerankerService | None = None
    if settings.reranker_enabled:
        reranker_service = RerankerService(settings)
        logger.info("Reranker enabled using model %s", settings.reranker_model_name)
    else:
        logger.info("Reranker disabled")

    retrieval_service = RetrievalService(settings, vector_store, embedding_service, reranker_service, llm_service)

    app.state.storage_provider = storage_provider
    app.state.vector_store = vector_store
    app.state.reranker_service = reranker_service
    app.state.ingest_service = IngestService(settings, vector_store, embedding_service, llm_service, storage_provider)
    app.state.document_service = DocumentService(settings, vector_store, storage_provider)
    app.state.job_status_service = JobStatusService()
    app.state.rag_pipeline = RAGPipeline(settings, retrieval_service, llm_service)

    # Native Industrial Multi-Agent Orchestrator
    sap_config = SAPConfig(_env_file=None)
    sap_client = SAPClient(sap_config)
    app.state.industrial_orchestrator = IndustrialOrchestrator(
        sap_client=sap_client,
        retrieval_service=retrieval_service,
    )

    logger.info("Application startup complete")



@app.on_event("shutdown")
async def on_shutdown() -> None:
    """Release external clients and other resources acquired at startup."""
    reranker_service = getattr(app.state, "reranker_service", None)
    if reranker_service:
        await reranker_service.close()
        logger.info("Closed RerankerService client")

    vector_store = getattr(app.state, "vector_store", None)
    if vector_store:
        await vector_store.close()
        logger.info("Closed MilvusStore connections")
