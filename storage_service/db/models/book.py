"""Book aggregate root — top-level document in the BOOKS collection.

Schema v3:
  * ``total_pages`` = sum of all pages across ALL chapter PDFs belonging
    to the book (not just a single PDF).
  * Each chapter's ``objects[]`` array holds one ``EmbeddedObject`` per
    page — the object contains both the MinIO storage reference and the
    extracted text metadata.
  * Each chapter carries its own ``processed_pages`` counter (int)
    tracking how many pages have been stored as PAGE_IMAGE objects.
  * The full chapter PDF reference is stored directly on the chapter
    (``pdf_object_key`` / ``pdf_bucket_name`` / ``pdf_object_url`` /
    ``pdf_size_bytes``), NOT inside ``objects[]``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from .base import MongoBase, istnow
from .embedded import EmbeddedChapter, EmbeddedObject


class Book(MongoBase):
    class_no: int
    subject: str
    title: str
    edition: Optional[str] = None
    academic_year: Optional[str] = None

    # Total pages across ALL chapter PDFs in this book.  Accumulated
    # during chapter PDF ingestion — each chapter's page count is added
    # to this total.
    total_pages: Optional[int] = None

    # Board and catalog metadata — populated when the book is imported
    # from the NCERT master catalog (newestbooks.json).
    board: Optional[str] = None
    catalog_source: Optional[str] = None

    # 1:1 embedded asset metadata — the source PDF uploaded to MinIO
    # (optional; only set when a full-book PDF is available).
    source_pdf: Optional[EmbeddedObject] = None

    # Embedded chapter aggregate.  Each chapter carries its own
    # ``objects`` array where each object represents one page of the
    # chapter's PDF (stored in MinIO) with extracted text metadata.
    chapters: list[EmbeddedChapter] = Field(default_factory=list)

    # Free-form metadata extracted from the PDF plus user-supplied tags.
    metadata: dict = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=istnow)
    updated_at: datetime = Field(default_factory=istnow)

    class Settings:
        collection = "BOOKS"
        indexes = [
            [("class_no", 1), ("subject", 1), ("title", 1)],
            [("chapters.chapter_no", 1)],
            [("chapters.id", 1)],
            [("chapters.pdf_filename", 1)],
            # Unique compound index to prevent duplicate Book documents.
            # Only one Book per (class_no, board, subject, title) combination.
            [("class_no", 1), ("board", 1), ("subject", 1), ("title", 1)],
        ]
