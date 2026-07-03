import logging
from redis import Redis
from rq import SimpleWorker, Queue
from backend.config.settings import get_settings

# Configure logging format for worker logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)

def main():
    settings = get_settings()
    logger.info("Initializing RQ SimpleWorker connected to Redis URL: %s", settings.redis_url)
    redis_conn = Redis.from_url(settings.redis_url)
    
    # Pass connection directly to both Queue and SimpleWorker
    queue = Queue("ingestion", connection=redis_conn)
    worker = SimpleWorker([queue], connection=redis_conn)
    worker.work()

if __name__ == '__main__':
    main()

