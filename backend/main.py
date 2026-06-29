import json
import logging
import os
import firebase_admin
from firebase_admin import credentials

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router as api_router
from backend.config.settings import get_settings
from backend.rag.embeddings import EmbeddingFactory
from backend.rag.llm import LLMService
from backend.rag.pipeline import RAGPipeline
from backend.rag.retrieval import RetrievalService
from backend.services.bm25_service import BM25Service
from backend.services.ingest_service import IngestService
from backend.services.reranker_service import RerankerService
from backend.vectordb.milvus_db import MilvusStore

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.on_event("startup")
async def on_startup() -> None:
    settings.resolved_upload_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Starting %s", settings.app_name)

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
    vector_store = MilvusStore(settings)
    llm_service = LLMService(settings)

    # BM25 sparse index (conditional on feature flag)
    bm25_service: BM25Service | None = None
    if settings.bm25_enabled:
        bm25_service = BM25Service(settings)
        logger.info("BM25 sparse search enabled")
    else:
        logger.info("BM25 sparse search disabled")

    # Reranker service
    reranker_service: RerankerService | None = None
    if settings.reranker_enabled:
        reranker_service = RerankerService(settings)
        logger.info("Reranker enabled using model %s", settings.reranker_model_name)
    else:
        logger.info("Reranker disabled")

    retrieval_service = RetrievalService(settings, vector_store, embedding_service, bm25_service, reranker_service)

    app.state.vector_store = vector_store
    app.state.bm25_service = bm25_service
    app.state.reranker_service = reranker_service
    app.state.ingest_service = IngestService(settings, vector_store, embedding_service, bm25_service)
    app.state.rag_pipeline = RAGPipeline(settings, retrieval_service, llm_service)

    logger.info("Application startup complete")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    reranker_service = getattr(app.state, "reranker_service", None)
    if reranker_service:
        await reranker_service.close()
        logger.info("Closed RerankerService client")
