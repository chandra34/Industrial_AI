from langchain_text_splitters import RecursiveCharacterTextSplitter
from backend.config.settings import Settings
from backend.rag.chunking import ChunkRecord
from backend.ingestion.parsers.utils.parser import PDFPage

class RecursiveChunker:
    """Wraps LangChain's RecursiveCharacterTextSplitter to perform character-based chunking."""
    
    def __init__(self, settings: Settings) -> None:
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def chunk(
        self,
        pages: list[PDFPage],
        document_id: str,
        source_filename: str,
    ) -> list[ChunkRecord]:
        chunks: list[ChunkRecord] = []
        running_index = 0

        for page in pages:
            if not page.text.strip():
                continue

            page_chunks = self.splitter.split_text(page.text)
            for chunk_text in page_chunks:
                normalized = chunk_text.strip()
                if not normalized:
                    continue

                chunks.append(
                    ChunkRecord(
                        document_id=document_id,
                        source_filename=source_filename,
                        page_number=page.page_number,
                        chunk_index=running_index,
                        text=normalized,
                    )
                )
                running_index += 1
                
        return chunks
