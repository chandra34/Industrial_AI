from dataclasses import dataclass
import logging
import re

import pymupdf as fitz

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PDFPage:
    page_number: int
    text: str


class PDFParseError(RuntimeError):
    pass


_whitespace_re = re.compile(r"[ \t\r\f\v]+")
_multiline_re = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    cleaned = text.replace("\u00a0", " ")
    cleaned = _whitespace_re.sub(" ", cleaned)
    cleaned = _multiline_re.sub("\n\n", cleaned)
    cleaned = "\n".join(line.strip() for line in cleaned.splitlines())
    cleaned = re.sub(r"\n{2,}", "\n\n", cleaned)
    return cleaned.strip()


def _extract_pages(document: fitz.Document) -> list[PDFPage]:
    pages: list[PDFPage] = []
    for index in range(document.page_count):
        page = document.load_page(index)
        text = normalize_text(page.get_text("text"))
        if text:
            pages.append(PDFPage(page_number=index + 1, text=text))
        else:
            logger.warning("Skipping empty page %s in PDF extraction", index + 1)
    return pages


def extract_pages_from_bytes(pdf_bytes: bytes) -> list[PDFPage]:
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
            return _extract_pages(document)
    except (fitz.FileDataError, fitz.FileNotFoundError, RuntimeError, ValueError) as exc:
        raise PDFParseError(f"Failed to parse PDF bytes: {exc}") from exc
