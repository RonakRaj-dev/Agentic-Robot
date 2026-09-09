"""PDF utilities for validation and metadata extraction.

PyMuPDF is used for:
    * opening PDFs
    * reading metadata
    * obtaining page dimensions
    * text extraction (via services/pymupdf/pymupdf_service.py)
    * splitting PDFs into single-page PDFs (via the ingestion pipeline)
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

try:
    import fitz

    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False
    logger.warning("PyMuPDF not available. Install: pip install PyMuPDF")


@contextmanager
def open_pdf_streaming(pdf_path: Path):
    """Context manager that opens a PDF and closes it on exit."""
    if not FITZ_AVAILABLE:
        raise ImportError("PyMuPDF required. pip install PyMuPDF")
    doc = None
    try:
        doc = fitz.open(str(pdf_path))
        yield doc
    except Exception as e:
        from core.exceptions import PDFCorruptedError, PDFValidationError

        if "file data error" in str(e).lower():
            raise PDFCorruptedError(f"PDF corrupted: {e}")
        raise PDFValidationError(f"Cannot open PDF: {e}")
    finally:
        if doc is not None:
            doc.close()


def validate_pdf(pdf_path: Path) -> bool:
    """Validate that the path is a non-empty, non-corrupted PDF."""
    from core.exceptions import PDFValidationError, PDFCorruptedError

    if not pdf_path.exists():
        raise PDFValidationError(f"File not found: {pdf_path}")
    if not pdf_path.is_file():
        raise PDFValidationError(f"Not a file: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise PDFValidationError(f"Not a PDF: {pdf_path.suffix}")
    max_size = 500 * 1024 * 1024
    file_size = pdf_path.stat().st_size
    if file_size == 0:
        raise PDFCorruptedError("PDF is empty")
    if file_size > max_size:
        raise PDFValidationError(f"PDF too large: {file_size} bytes")
    with open_pdf_streaming(pdf_path) as doc:
        if doc.page_count == 0:
            raise PDFCorruptedError("PDF has no pages")
        try:
            _ = doc[0].rect
        except Exception as e:
            raise PDFCorruptedError(f"Cannot read first page: {e}")
        page_count = doc.page_count
    logger.info(f"PDF valid: {pdf_path.name} ({file_size} bytes, {page_count} pages)")
    return True


def extract_pdf_metadata(pdf_path: Path) -> Dict[str, Any]:
    """Read PDF metadata + first-page dimensions via PyMuPDF."""
    from core.exceptions import MetadataExtractionError

    try:
        with open_pdf_streaming(pdf_path) as doc:
            meta = doc.metadata or {}
            result: Dict[str, Any] = {
                "page_count": doc.page_count,
                "title": meta.get("title") or None,
                "author": meta.get("author") or None,
                "subject": meta.get("subject") or None,
                "creator": meta.get("creator") or None,
                "producer": meta.get("producer") or None,
                "creation_date": meta.get("creationDate") or None,
                "modification_date": meta.get("modDate") or None,
                "encrypted": doc.is_encrypted,
                "file_size_bytes": pdf_path.stat().st_size,
            }
            if doc.page_count > 0:
                first_page = doc[0]
                result["page_width"] = first_page.rect.width
                result["page_height"] = first_page.rect.height
            return result
    except Exception as e:
        raise MetadataExtractionError(f"Failed to extract metadata: {e}")