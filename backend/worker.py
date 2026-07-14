import logging
import os
from redis import Redis
from rq import Worker, SimpleWorker, Queue
from backend.config.settings import get_settings

# Configure logging format for worker logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)

def main():
    settings = get_settings()
    logger.info("Initializing RQ Worker connected to Redis URL: %s", settings.redis_url)
    redis_conn = Redis.from_url(settings.redis_url)
    
    # Pass connection directly to both Queue and Worker
    from rq.serializers import JSONSerializer
    queue = Queue("ingestion", connection=redis_conn, serializer=JSONSerializer)
    
    if os.name == "nt":
        logger.info("Detected Windows OS: using SimpleWorker (in-process execution, no job isolation)")
        worker = SimpleWorker([queue], connection=redis_conn, serializer=JSONSerializer)
    else:
        logger.info("Detected Unix/Linux OS: using standard Worker (fork-based execution with job isolation)")
        worker = Worker([queue], connection=redis_conn, serializer=JSONSerializer)
        
    # Pre-warm heavy parser models in parent worker process before starting work
    parser_type = settings.document_parser.lower().strip()
    if parser_type == "docling":
        logger.info("Pre-warming Docling parser in parent worker process to cache models...")
        try:
            from backend.ingestion.pipeline import get_parser
            get_parser(settings)
            logger.info("Docling parser pre-warmed successfully.")
        except Exception as exc:
            logger.warning("Failed to pre-warm Docling parser: %s. Continuing worker initialization...", exc)
            
    worker.work()

if __name__ == '__main__':
    main()

