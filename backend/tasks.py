import asyncio
import logging
from backend.config.settings import get_settings
from backend.services.ingest_service import IngestService
from backend.services.job_status_service import JobStatusService
from backend.rag.embeddings import EmbeddingFactory
from backend.vectordb.milvus_db import MilvusStore
from backend.database.session import SessionLocal
from backend.schemas.schemas import UploadResponse

logger = logging.getLogger(__name__)

def run_ingest_task(job_id: str, file_bytes_b64: str, filename: str, user_id: str) -> None:
    """Synchronous task wrapper called by the RQ worker.
    
    Bridges RQ's synchronous execution with the async ingestion pipeline using asyncio.run.
    """
    logger.info("Starting background ingestion task for job: %s, file: %s", job_id, filename)
    try:
        asyncio.run(async_run_ingest_task(job_id, file_bytes_b64, filename, user_id))
    except Exception as exc:
        logger.exception("Failed to run async_run_ingest_task for job: %s", job_id)
        raise exc

async def async_run_ingest_task(job_id: str, file_bytes_b64: str, filename: str, user_id: str) -> None:
    """Asynchronous worker function that handles client initialization and runs document ingestion."""
    settings = get_settings()
    
    # Initialize standalone connections for this worker task process
    embedding_service = EmbeddingFactory.create(settings)
    vector_store = MilvusStore(settings)
    ingest_service = IngestService(settings, vector_store, embedding_service)
    job_status_service = JobStatusService()
    
    # Decode the base64 payload to binary bytes for parsing
    import base64
    file_bytes = base64.b64decode(file_bytes_b64)
    
    db = SessionLocal()
    try:
        job_status_service.update_status(db, job_id, "processing")
        
        # Execute the main ingestion steps (parse, chunk, embed, store, metadata db write)
        result = await ingest_service.ingest_pdf(file_bytes, filename, user_id, db=db)
        
        upload_response = UploadResponse(
            document_id=result.document_id,
            filename=result.filename,
            stored_path=result.stored_path,
            page_count=result.page_count,
            chunk_count=result.chunk_count,
            embedded_count=result.embedded_count,
        )
        job_status_service.update_status(db, job_id, "completed", result=upload_response)
        logger.info("Background ingestion task completed successfully for job: %s", job_id)
    except Exception as exc:
        logger.exception("Background ingestion failed for job: %s, file: %s", job_id, filename)
        job_status_service.update_status(db, job_id, "failed", error=str(exc))
        raise exc
    finally:
        db.close()
        try:
            await vector_store.close()
            logger.info("Closed MilvusStore connection in background worker task")
        except Exception as store_exc:
            logger.warning("Error closing MilvusStore connection in background worker: %s", store_exc)
