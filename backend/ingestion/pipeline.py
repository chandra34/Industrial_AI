from backend.config.settings import Settings
from backend.ingestion.parsers.base import BaseParser
from backend.ingestion.parsers.pymupdf_parser import PyMuPDFParser
from backend.ingestion.parsers.docling_parser import DoclingParser

# Cache parser instances to avoid re-initializing heavy objects (like Docling's DocumentConverter) on every upload
_parser_cache: dict[str, BaseParser] = {}

def get_parser(settings: Settings) -> BaseParser:
    """Factory function to return the configured document parser."""
    parser_type = settings.document_parser.lower().strip()
    if parser_type not in _parser_cache:
        if parser_type == "docling":
            _parser_cache[parser_type] = DoclingParser(settings)
        else:
            _parser_cache[parser_type] = PyMuPDFParser(settings)
    return _parser_cache[parser_type]
