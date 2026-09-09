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
    total_pages: Optional[int] = None

    # 1:1 embedded asset metadata — the source PDF uploaded to MinIO.
    source_pdf: Optional[EmbeddedObject] = None

    # Embedded chapter aggregate. Each chapter carries its own
    # `objects` (page-image metadata) and `ocr_pages` (OCR text).
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
        ]
