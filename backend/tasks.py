import asyncio
import logging
from backend.config.settings import get_settings
from backend.services.ingest_service import IngestService
from backend.services.job_status_service import JobStatusService
from backend.services.storage import create_storage_provider
from backend.rag.embeddings import EmbeddingFactory
from backend.vectordb.milvus_db import MilvusStore
from backend.database.session import AsyncSessionLocal
from backend.schemas.documents import UploadResponse

logger = logging.getLogger(__name__)

def run_ingest_task(job_id: str, file_key: str, filename: str, user_id: str, metadata: dict | None = None) -> None:
    """Synchronous task wrapper called by the RQ worker.
    
    Bridges RQ's synchronous execution with the async ingestion pipeline using asyncio.run.
    """
    logger.info("Starting background ingestion task for job: %s, file: %s", job_id, filename)
    try:
        asyncio.run(async_run_ingest_task(job_id, file_key, filename, user_id, metadata))
    except Exception as exc:
        logger.exception("Failed to run async_run_ingest_task for job: %s", job_id)
        raise exc

async def async_run_ingest_task(job_id: str, file_key: str, filename: str, user_id: str, metadata: dict | None = None) -> None:
    """Asynchronous worker function that handles client initialization and runs document ingestion."""
    settings = get_settings()
    
    from backend.rag.llm import LLMFactory
    
    # Initialize standalone connections for this worker task process
    embedding_service = EmbeddingFactory.create(settings)
    vector_store = MilvusStore(settings)
    llm_service = LLMFactory.create(settings)
    storage_provider = create_storage_provider(settings)
    ingest_service = IngestService(settings, vector_store, embedding_service, llm_service, storage_provider)
    job_status_service = JobStatusService()
    
    # Download the temporary upload from storage
    logger.info("Downloading file %s from temporary storage for ingestion", file_key)
    file_bytes = await storage_provider.download_file(file_key)
    
    # Clean up the temporary file from storage
    try:
        await storage_provider.delete_file(file_key)
        logger.info("Deleted temporary upload file: %s", file_key)
    except Exception as cleanup_exc:
        logger.warning("Failed to delete temporary file %s: %s", file_key, cleanup_exc)
    
    async with AsyncSessionLocal() as db:
        try:
            await job_status_service.update_status(db, job_id, "processing")
            
            # Execute the main ingestion steps (parse, chunk, embed, store, metadata db write)
            result = await ingest_service.ingest_pdf(file_bytes, filename, user_id, db=db, metadata=metadata)
            
            upload_response = UploadResponse(
                document_id=result.document_id,
                filename=result.filename,
                stored_path=result.stored_path,
                page_count=result.page_count,
                chunk_count=result.chunk_count,
                embedded_count=result.embedded_count,
                document_type=result.document_type,
                manufacturer=result.manufacturer,
                equipment=result.equipment,
            )
            await job_status_service.update_status(db, job_id, "completed", result=upload_response)
            logger.info("Background ingestion task completed successfully for job: %s", job_id)
        except Exception as exc:
            logger.exception("Background ingestion failed for job: %s, file: %s", job_id, filename)
            await db.rollback()
            await job_status_service.update_status(db, job_id, "failed", error=str(exc))
            raise exc
        finally:
            try:
                await vector_store.close()
                logger.info("Closed MilvusStore connection in background worker task")
            except Exception as store_exc:
                logger.warning("Error closing MilvusStore connection in background worker: %s", store_exc)
