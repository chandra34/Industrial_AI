from io import BytesIO
from docling.datamodel.base_models import DocumentStream, InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend

from backend.config.settings import Settings
from backend.ingestion.parsers.base import BaseParser
from backend.ingestion.chunkers.docling_hybrid import DoclingHybridChunker
from backend.rag.chunking import ChunkRecord

class DoclingParser(BaseParser):
    """Parses document bytes using Docling and chunks with HybridChunker."""
    
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        
        # Configure Docling pipeline options dynamically from settings
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = self.settings.docling_do_ocr
        if pipeline_options.do_ocr:
            pipeline_options.ocr_options = EasyOcrOptions()
            
        pipeline_options.do_formula_enrichment = self.settings.docling_do_formula_enrichment
        
        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options,
                    backend=PyPdfiumDocumentBackend
                )
            }
        )
        self.chunker = DoclingHybridChunker(settings)

    def parse(
        self,
        pdf_bytes: bytes,
        document_id: str,
        source_filename: str,
        metadata: dict | None = None,
    ) -> list[ChunkRecord]:
        byte_stream = BytesIO(pdf_bytes)
        source = DocumentStream(name=source_filename, stream=byte_stream)
        
        result = self.converter.convert(source)
        return self.chunker.chunk(result.document, document_id, source_filename, metadata=metadata)
