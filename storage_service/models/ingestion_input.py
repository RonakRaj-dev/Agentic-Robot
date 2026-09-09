"""Input models for the legacy single-PDF ingestion path (``ingest.py``).

The catalog-driven path (``ingest_catalog.py``) does NOT use these —
it goes through :class:`CatalogImportService` which builds Book
documents directly from the catalog JSON.

These models are kept for backwards compatibility with the original
``ingest.py`` CLI.  The dead ``ChapterMetadata`` and
``ProcessingOptions`` classes that used to live here were removed
(neither was ever populated by any caller).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class BookMetadata(BaseModel):
    """Metadata for a single-PDF book (legacy ``ingest.py`` path)."""

    title: str = Field(..., min_length=1)
    subtitle: Optional[str] = None
    author: Optional[str] = None
    publisher: Optional[str] = None
    publication_year: Optional[int] = Field(None, ge=1900, le=2100)
    isbn: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IngestionInput(BaseModel):
    """Input for :meth:`IngestionPipeline.ingest` (legacy single-PDF path).

    The catalog-driven path uses :meth:`IngestionPipeline.ingest_chapter`
    instead, which takes ``pdf_path`` / ``book_id`` / ``chapter_no``
    directly.
    """

    pdf_path: Path = Field(...)
    book_metadata: BookMetadata = Field(...)
    class_level: str = Field(...)
    subject: str = Field(...)
    language: str = Field(default="en")
    board: str = Field(default="NCERT")
    processing_options: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("pdf_path")
    @classmethod
    def pdf_path_must_exist(cls, v):
        path = Path(v) if isinstance(v, str) else v
        if not path.exists():
            raise ValueError(f"PDF file not found: {path}")
        if not path.is_file():
            raise ValueError(f"Path is not a file: {path}")
        if path.suffix.lower() != ".pdf":
            raise ValueError(f"File must be a PDF, got: {path.suffix}")
        return path
