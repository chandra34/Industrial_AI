import logging
from docling.chunking import HybridChunker
from docling_core.types.doc import DoclingDocument
from backend.config.settings import Settings
from backend.rag.chunking import ChunkRecord

logger = logging.getLogger(__name__)

class DoclingHybridChunker:
    """Structure-aware hybrid chunker using Docling."""
    
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        # Instantiate HybridChunker with character-to-token heuristic (max_tokens = settings.chunk_size // 4)
        self.chunker = HybridChunker(
            max_tokens=max(128, settings.chunk_size // 4)
        )

    def chunk(
        self,
        doc: DoclingDocument,
        document_id: str,
        source_filename: str,
        metadata: dict | None = None,
    ) -> list[ChunkRecord]:
        chunks: list[ChunkRecord] = []
        running_index = 0

        meta = metadata or {}
        doc_type = meta.get("document_type")
        mfr = meta.get("manufacturer")
        equip = meta.get("equipment")
        rev = meta.get("revision")
        lang = meta.get("language")

        docling_chunks = self.chunker.chunk(doc)
        for dl_chunk in docling_chunks:
            text = dl_chunk.text.strip()
            if not text:
                continue

            # Extract page number from first provenance item if available, default to 1
            page_number = 1
            if dl_chunk.meta.doc_items:
                for item in dl_chunk.meta.doc_items:
                    if item.prov:
                        page_number = item.prov[0].page_no
                        break
            
            # Extract section context
            section_name = ""
            if dl_chunk.meta.headings:
                section_name = " > ".join(dl_chunk.meta.headings)

            # Prepend section metadata to chunk text to improve RAG retrieval accuracy 
            # while keeping schema compatible
            formatted_text = text
            if section_name:
                formatted_text = f"[{section_name}]\n{text}"

            chunks.append(
                ChunkRecord(
                    document_id=document_id,
                    source_filename=source_filename,
                    page_number=page_number,
                    chunk_index=running_index,
                    text=formatted_text,
                    document_type=doc_type,
                    manufacturer=mfr,
                    equipment=equip,
                    section=section_name,
                    revision=rev,
                    language=lang,
                    paragraph="",
                )
            )
            running_index += 1

        return chunks
