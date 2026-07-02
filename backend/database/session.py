"""SQLAlchemy engine, session factory, and FastAPI dependency for database access."""

import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from backend.config.settings import get_settings

logger = logging.getLogger(__name__)

_settings = get_settings()
engine = create_engine(
    _settings.database_url,
    connect_args={"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {},
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """FastAPI dependency that yields a database session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
