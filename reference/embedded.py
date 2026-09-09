from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field

from .base import PyObjectId, istnow


class ExtractionMethod(str, Enum):
    """OCR engine that produced the text."""

    UNLIMITED_OCR = "unlimited_ocr"


class ObjectType(str, Enum):
    """Type of binary object stored in MinIO."""

    PAGE_IMAGE = "PAGE_IMAGE"
    PDF = "PDF"
    FIGURE = "FIGURE"
    EXPORT = "EXPORT"
    SNAPSHOT = "SNAPSHOT"


def _new_object_id() -> ObjectId:
    return ObjectId()


class _EmbeddedBase(BaseModel):
    """Common config for embedded sub-documents.

    Embedded documents allow ObjectId types but do NOT carry an `_id`
    alias — they only carry their own `id` field which is stored as `id`
    (not `_id`) inside the parent array.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        extra="ignore",
    )

    def to_mongo(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)


class EmbeddedObject(_EmbeddedBase):
    id: PyObjectId = Field(default_factory=_new_object_id)
    object_type: ObjectType
    object_key: str
    bucket_name: str
    object_url: Optional[str] = None
    page_no: Optional[int] = None
    mime_type: str
    size_bytes: int
    etag: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=istnow)


class EmbeddedOCRPage(_EmbeddedBase):
    id: PyObjectId = Field(default_factory=_new_object_id)
    page_number: int
    text: str
    word_count: int = 0
    token_count: int = 0
    contains_math: bool = False
    contains_table: bool = False
    contains_figure_caption: bool = False
    extraction_method: ExtractionMethod = ExtractionMethod.UNLIMITED_OCR
    created_at: datetime = Field(default_factory=istnow)


class EmbeddedChapter(_EmbeddedBase):
    id: PyObjectId = Field(default_factory=_new_object_id)
    chapter_no: int
    title: str
    summary: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    objects: list[EmbeddedObject] = Field(default_factory=list)
    ocr_pages: list[EmbeddedOCRPage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=istnow)
    updated_at: datetime = Field(default_factory=istnow)
