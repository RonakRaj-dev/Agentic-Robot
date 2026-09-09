"""Object service interface.

In the BOOKS-aggregate-root schema, objects (PAGE_IMAGE / SOURCE_PDF /
FIGURE / EXPORT) live inside ``chapters[].objects[]``.  This interface
exposes object-lifecycle operations as a thin facade over
``IBookService`` so callers that think in terms of "objects" (rather
than "chapters") do not need to know about the embedding.

The MVP architecture document lists this as the "Objects stored in
chapters" service.  It is intentionally NOT a separate collection —
all writes still go through ``IBookService`` to preserve the aggregate
root invariant.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class IObjectService(ABC):
    """Chapter-embedded object lifecycle facade.

    All methods delegate to :class:`IBookService` so the BOOKS aggregate
    root remains the single write surface.
    """

    @abstractmethod
    async def append_page_image(
        self,
        book_id: str,
        chapter_id: str,
        page_no: int,
        object_key: str,
        bucket_name: str,
        size_bytes: int,
        plain_text: str = "",
        word_count: int = 0,
        token_count: int = 0,
        extraction_method: str = "pymupdf",
        mime_type: str = "image/png",
        object_url: Optional[str] = None,
    ) -> str:
        """Append a PAGE_IMAGE object to ``chapter.objects[]``.

        Returns the new object_id as a string.

        .. versionchanged:: v6
            ``object_url`` is now optional and defaults to ``None``.
            New callers SHOULD NOT pass a URL — persistent URLs are no
            longer stored.

        .. versionchanged:: v7
            Presigned URL generation has been removed.  Callers that
            need an access URL must use
            :meth:`IStorageService.get_public_url` with the
            ``bucket_name`` + ``object_key`` fields.
        """
        ...

    @abstractmethod
    async def append_source_pdf(
        self,
        book_id: str,
        file_path: Any,
        metadata: dict[str, Any],
        storage_url: Optional[str] = None,
        bucket_name: Optional[str] = None,
        object_key: Optional[str] = None,
    ) -> str:
        """Attach a source-PDF asset to the Book document.

        .. versionchanged:: v6
            Callers should now pass ``bucket_name`` + ``object_key``
            instead of ``storage_url``.  ``storage_url`` is retained
            for backward compatibility — when provided, it is parsed
            via :func:`utils.oid_utils.parse_storage_url` to derive
            ``bucket_name`` + ``object_key``.  When both are provided,
            the structured fields take precedence.
        """
        ...

    @abstractmethod
    async def list_chapter_objects(
        self,
        book_id: str,
        chapter_id: str,
    ) -> list[dict[str, Any]]:
        """Return all objects in ``chapter.objects[]`` as plain dicts."""
        ...

    @abstractmethod
    async def clear_chapter_objects(
        self,
        book_id: str,
        chapter_id: str,
    ) -> bool:
        """Empty the chapter's ``objects[]`` array."""
        ...

    @abstractmethod
    async def get_object(
        self,
        book_id: str,
        chapter_id: str,
        object_id: str,
    ) -> Optional[dict[str, Any]]:
        """Return a single object by id, or None."""
        ...
