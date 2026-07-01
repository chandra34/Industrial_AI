from abc import ABC, abstractmethod
from backend.rag.chunking import ChunkRecord

class BaseParser(ABC):
    """Abstract interface for all document parsers."""

    @abstractmethod
    def parse(
        self,
        pdf_bytes: bytes,
        document_id: str,
        source_filename: str,
    ) -> list[ChunkRecord]:
        """Parse pdf bytes and return a unified list of ChunkRecord objects."""
        pass
