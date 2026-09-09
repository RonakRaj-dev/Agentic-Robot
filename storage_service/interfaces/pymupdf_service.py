"""PyMuPDF text-extraction service interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class IPyMuPDFService(ABC):
    """PyMuPDF text-extraction abstraction.

    Implementations wrap the ``fitz`` (PyMuPDF) library and expose a
    single method — ``extract_pages`` — that takes a PDF path and
    returns per-page text extraction results.

    PyMuPDF operates page-by-page (streaming) and does not perform layout
    analysis, OCR, or image extraction.  It simply calls
    ``page.get_text()`` on each page.
    """

    @abstractmethod
    async def extract_pages(
        self,
        pdf_path: Path,
        book_id: str = "",
    ) -> dict[str, Any]:
        """Extract text from every page of a PDF using PyMuPDF.

        Returns a dict with:
        * ``pages``       — list[dict]: per-page text data
        * ``total_pages`` — int
        """
        ...
