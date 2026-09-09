"""MongoDB-backed Object service — a facade over :class:`MongoBookService`.

In the BOOKS-aggregate-root schema, objects (PAGE_IMAGE / SOURCE_PDF /
FIGURE / EXPORT) live inside ``chapters[].objects[]``.  This service
exposes object-lifecycle operations as a thin facade so callers that
think in terms of "objects" do not need to know about the embedding.

All writes still go through :class:`MongoBookService` to preserve the
aggregate-root invariant — no component updates embedded chapter data
directly.

.. versionchanged:: v6
    ``append_page_image`` accepts an optional ``object_url`` (defaults
    to ``None``).  ``append_source_pdf`` accepts structured
    ``bucket_name`` + ``object_key`` instead of requiring a URL.

.. versionchanged:: v7
    Presigned URL generation has been removed.  Callers that need an
    access URL for an object must use
    :meth:`IStorageService.get_public_url` with the structured
    ``bucket_name`` + ``object_key`` fields.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from db.models.embedded import EmbeddedObject, ObjectType, ExtractionMethod
from interfaces.object_service import IObjectService
from interfaces.book_service import IBookService
from utils.oid_utils import to_oid


class MongoObjectService(IObjectService):
    """Concrete Object service — facade over :class:`IBookService`."""

    def __init__(self, book_service: Optional[IBookService] = None) -> None:
        # Lazy import to avoid circular dependency at module load time.
        if book_service is None:
            from services.mongo.book_service import MongoBookService
            book_service = MongoBookService()
        self._books = book_service

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
        return await self._books.append_processed_page(
            book_id=book_id,
            chapter_id=chapter_id,
            page_no=page_no,
            plain_text=plain_text,
            word_count=word_count,
            token_count=token_count,
            extraction_method=extraction_method,
            object_key=object_key,
            bucket_name=bucket_name,
            object_url=object_url,
            size_bytes=size_bytes,
            mime_type=mime_type,
        )

    async def append_source_pdf(
        self,
        book_id: str,
        file_path: Path,
        metadata: dict[str, Any],
        storage_url: Optional[str] = None,
        bucket_name: Optional[str] = None,
        object_key: Optional[str] = None,
    ) -> str:
        return await self._books.attach_source_pdf(
            book_id=book_id,
            file_path=file_path,
            metadata=metadata,
            storage_url=storage_url,
            bucket_name=bucket_name,
            object_key=object_key,
        )

    async def list_chapter_objects(
        self,
        book_id: str,
        chapter_id: str,
    ) -> list[dict[str, Any]]:
        """Return all objects in ``chapter.objects[]`` as plain dicts."""
        book = await self._books.get_book(book_id)
        if book is None:
            return []
        if isinstance(book, dict):
            chapters = book.get("chapters") or []
        else:
            chapters = getattr(book, "chapters", []) or []
        for ch in chapters:
            ch_id = ch.get("id") if isinstance(ch, dict) else str(getattr(ch, "id", ""))
            if str(ch_id) == str(chapter_id):
                objs = ch.get("objects") if isinstance(ch, dict) else getattr(ch, "objects", [])
                result = []
                for o in objs:
                    if isinstance(o, dict):
                        result.append(o)
                    else:
                        # Pydantic model — serialize.
                        result.append(o.model_dump() if hasattr(o, "model_dump") else dict(o))
                return result
        return []

    async def clear_chapter_objects(
        self,
        book_id: str,
        chapter_id: str,
    ) -> bool:
        return await self._books.clear_chapter_objects(
            book_id=book_id, chapter_id=chapter_id,
        )

    async def get_object(
        self,
        book_id: str,
        chapter_id: str,
        object_id: str,
    ) -> Optional[dict[str, Any]]:
        objs = await self.list_chapter_objects(book_id, chapter_id)
        for o in objs:
            oid = o.get("id") if isinstance(o, dict) else None
            if str(oid) == str(object_id):
                return o
        return None
