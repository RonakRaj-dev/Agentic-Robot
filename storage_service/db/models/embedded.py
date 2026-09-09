"""Embedded sub-document models for the Book aggregate root.

Schema v3 — page-image storage design:

Each chapter stores:
  * The full chapter PDF reference directly on the chapter document
    (``pdf_object_key``, ``pdf_bucket_name``, ``pdf_object_url``,
    ``pdf_size_bytes``).
  * A ``objects[]`` array containing one ``EmbeddedObject`` (PAGE_IMAGE)
    per page.  Each object holds:
      - The MinIO storage reference for the PNG image
      - Page metadata (page_no, mime_type, size_bytes)
      - Extracted text data in ``metadata`` (plain_text, word_count,
        token_count, extraction_method)
  * A ``processed_pages`` counter tracking how many pages have been
    processed.

There is NO separate CHAPTERS collection and NO separate OBJECTS
collection — everything is embedded inside the BOOKS document.

.. versionchanged:: v6
    The ``object_url`` and ``pdf_object_url`` fields are now
    **deprecated** — they are kept as ``Optional[str]`` only so old
    records (which contain stored URLs) still deserialise cleanly.
    New uploads do NOT populate these fields.  Callers that need an
    access URL must request a public URL via
    :meth:`IStorageService.get_public_url` using the
    structured ``bucket_name`` + ``object_key`` fields.

    The runtime compatibility helper
    :func:`utils.storage_compat.resolve_object_ref` returns
    ``(bucket, object_key)`` for any record — old or new — by parsing
    the legacy URL field as a fallback.

.. versionchanged:: v7
    Presigned URL generation has been removed entirely.  The MinIO
    buckets are publicly downloadable and access URLs are built
    on demand by :meth:`IStorageService.get_public_url` from
    ``Settings.public_storage_url``.  No URLs are persisted.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field

from .base import PyObjectId, istnow


class ExtractionMethod(str, Enum):
    """Document processing engine that produced the page text."""

    PYMUPDF = "pymupdf"


class ObjectType(str, Enum):
    """Type of binary object stored in MinIO."""

    PAGE_IMAGE = "PAGE_IMAGE"    # PNG image rendered from a chapter PDF page
    SOURCE_PDF = "SOURCE_PDF"    # full source PDF (book-level)
    FIGURE = "FIGURE"            # extracted figure image


def _new_object_id() -> ObjectId:
    return ObjectId()


class _EmbeddedBase(BaseModel):
    """Common config for embedded sub-documents.

    Embedded documents allow ObjectId types but do NOT carry an ``_id``
    alias — they only carry their own ``id`` field which is stored as ``id``
    (not ``_id``) inside the parent array.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        extra="ignore",
    )

    def to_mongo(self) -> dict[str, Any]:
        data = self.model_dump(by_alias=True, exclude_none=True)
        for field_name, fi in self.model_fields.items():
            val = data.get(field_name)
            if val is None:
                continue
            if (
                fi.annotation is ObjectId
                and isinstance(val, str)
                and ObjectId.is_valid(val)
            ):
                data[field_name] = ObjectId(val)
        return data


class EmbeddedObject(_EmbeddedBase):
    """A stored asset reference — the primary building block for page data.

    Each page in a chapter PDF produces one ``EmbeddedObject`` entry
    inside ``chapter.objects[]``.  The object carries:

    * MinIO storage reference: ``object_key``, ``bucket_name`` —
      **the only fields a consumer needs to build a public URL**.
    * Page metadata: ``page_no``, ``mime_type``, ``size_bytes``
    * Extracted text data in ``metadata``: ``plain_text``,
      ``word_count``, ``token_count``, ``extraction_method``

    .. versionchanged:: v6
        ``object_url`` is deprecated.  New uploads leave it as ``None``.
        Old records may still contain a stored URL — use
        :func:`utils.storage_compat.resolve_object_ref` to extract
        ``(bucket, object_key)`` uniformly from old and new records.

    .. versionchanged:: v7
        Callers that need an access URL must call
        :meth:`IStorageService.get_public_url` with the structured
        ``bucket_name`` + ``object_key`` fields.  Presigned URL
        generation has been removed.
    """
    id: PyObjectId = Field(default_factory=_new_object_id)
    object_type: ObjectType
    object_key: str
    bucket_name: str
    object_url: Optional[str] = None  # DEPRECATED in v6 — kept for backward compat
    page_no: Optional[int] = None
    mime_type: str
    size_bytes: int
    etag: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=istnow)


class EmbeddedChapter(_EmbeddedBase):
    """A chapter embedded inside a Book document.

    The chapter stores:
      * The full chapter PDF reference (uploaded once to MinIO).
      * A ``objects[]`` array holding one PAGE_IMAGE entry per page.
      * A ``processed_pages`` counter tracking processed page count.

    .. versionchanged:: v6
        ``pdf_object_url`` is deprecated.  New uploads leave it as
        ``None``.  Old records may still contain a stored URL — use
        :func:`utils.storage_compat.resolve_chapter_pdf_ref` to extract
        ``(bucket, object_key)`` uniformly from old and new records.

    .. versionchanged:: v7
        Callers that need an access URL must call
        :meth:`IStorageService.get_public_url` with the structured
        ``pdf_bucket_name`` + ``pdf_object_key`` fields.  Presigned URL
        generation has been removed.
    """
    id: PyObjectId = Field(default_factory=_new_object_id)
    chapter_no: int
    title: str
    summary: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None

    # Catalog-driven metadata — populated when the book is imported from
    # the NCERT master catalog (newestbooks.json).
    pdf_filename: Optional[str] = None
    chapter_code: Optional[str] = None
    preferred_llm: Optional[str] = None
    catalog_source: Optional[str] = None

    # Chapter PDF storage — the full chapter PDF uploaded once to MinIO.
    # The PDF reference is stored directly on the chapter, NOT inside
    # objects[].  objects[] only contains page images.
    #
    # v6: ``pdf_object_url`` is DEPRECATED.  New uploads leave it as
    # None.  ``pdf_bucket_name`` + ``pdf_object_key`` are the canonical
    # storage reference.
    pdf_object_key: Optional[str] = None
    pdf_bucket_name: Optional[str] = None
    pdf_object_url: Optional[str] = None  # DEPRECATED in v6
    pdf_size_bytes: Optional[int] = None

    # One PAGE_IMAGE entry per page in the chapter PDF.  Each entry
    # contains the MinIO storage reference for the PNG image and the
    # extracted text metadata.
    objects: list[EmbeddedObject] = Field(default_factory=list)

    # Counter of processed pages for this chapter.
    processed_pages: int = 0

    created_at: datetime = Field(default_factory=istnow)
    updated_at: datetime = Field(default_factory=istnow)
