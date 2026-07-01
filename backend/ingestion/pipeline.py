from backend.config.settings import Settings
from backend.ingestion.parsers.base import BaseParser
from backend.ingestion.parsers.pymupdf_parser import PyMuPDFParser
from backend.ingestion.parsers.docling_parser import DoclingParser

def get_parser(settings: Settings) -> BaseParser:
    """Factory function to return the configured document parser."""
    parser_type = settings.document_parser.lower().strip()
    if parser_type == "docling":
        return DoclingParser(settings)
    return PyMuPDFParser(settings)
