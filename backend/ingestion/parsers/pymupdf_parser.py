from backend.config.settings import Settings
from backend.ingestion.parsers.base import BaseParser
from backend.ingestion.chunkers.recursive import RecursiveChunker
from backend.ingestion.parsers.utils.parser import extract_pages_from_bytes
from backend.rag.chunking import ChunkRecord

class PyMuPDFParser(BaseParser):
    """Parses PDF using PyMuPDF and chunks with RecursiveCharacterTextSplitter."""
    
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.chunker = RecursiveChunker(settings)

    def parse(
        self,
        pdf_bytes: bytes,
        document_id: str,
        source_filename: str,
    ) -> list[ChunkRecord]:
        pages = extract_pages_from_bytes(pdf_bytes)
        return self.chunker.chunk(pages, document_id, source_filename)
