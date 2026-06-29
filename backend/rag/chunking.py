from dataclasses import dataclass
import logging

from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.config.settings import Settings
from backend.pdf.parser import PDFPage

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ChunkRecord:
    document_id: str
    source_filename: str
    page_number: int
    chunk_index: int
    text: str


def chunk_pages(
    pages: list[PDFPage],
    document_id: str,
    source_filename: str,
    settings: Settings,
) -> list[ChunkRecord]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks: list[ChunkRecord] = []
    running_index = 0

    for page in pages:
        if not page.text.strip():
            continue

        page_chunks = splitter.split_text(page.text)
        if not page_chunks:
            logger.warning("Page %s produced no chunks", page.page_number)
            continue

        for chunk_text in page_chunks:
            normalized_chunk = chunk_text.strip()
            if not normalized_chunk:
                continue

            chunks.append(
                ChunkRecord(
                    document_id=document_id,
                    source_filename=source_filename,
                    page_number=page.page_number,
                    chunk_index=running_index,
                    text=normalized_chunk,
                )
            )
            running_index += 1

    return chunks
