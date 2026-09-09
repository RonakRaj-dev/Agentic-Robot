from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from bson import ObjectId

from core.logging import get_logger
from db.models.base import PyObjectId
from db.models.book import Book
from db.models.embedded import EmbeddedChapter, EmbeddedObject
from utils.oid_utils import to_oid
from .base_mongo_repo import BaseMongoRepository

logger = get_logger(__name__)


class BookRepository(BaseMongoRepository[Book]):
    """Repository for the BOOKS aggregate root.

    All chapter and chapter-object mutations are atomic single-write
    operations that target the chapter via the positional operator
    (``chapters.$``).  Batch appends use ``$push`` with ``$each`` so a
    whole chapter's worth of page objects can be persisted in one
    round trip instead of one-per-page.
    """

    collection_name = "BOOKS"
    model_class = Book

    # ── read paths ───────────────────────────────────────────────────

    async def find_by_identity(
        self,
        class_no: int,
        subject: str,
        title: Optional[str] = None,
        board: str | None = None,
    ) -> Book | None:
        """Find a book by its unique identity (class + subject + title + board).

        This is the idempotent lookup used during catalog import to prevent
        duplicate Book documents.
        """
        filter_: dict[str, Any] = {
            "class_no": class_no,
            "subject": subject,
        }
        if title is not None:
            filter_["title"] = title
        if board is not None:
            filter_["board"] = board
        results = await self.find_many(filter_, limit=1)
        return results[0] if results else None

    async def find_chapter_by_pdf_filename(
        self,
        pdf_filename: str,
    ) -> dict[str, Any] | None:
        """Find a book and chapter by the chapter's pdf_filename.

        Returns ``{"book_id": ..., "chapter_no": ...}`` or None.
        """
        doc = await self._col.find_one(
            {"chapters.pdf_filename": pdf_filename},
            projection={
                "_id": 1,
                "chapters.$": 1,
            },
        )
        if not doc or not doc.get("chapters"):
            return None
        return {
            "book_id": doc["_id"],
            "chapter_no": doc["chapters"][0].get("chapter_no"),
        }

    async def find_chapter_by_no(
        self, book_id: PyObjectId, chapter_no: int
    ) -> dict[str, Any] | None:
        """Return only the matching chapter sub-document."""
        doc = await self._col.find_one(
            {"_id": self._oid(book_id), "chapters.chapter_no": chapter_no},
            projection={"chapters.$": 1},
        )
        if not doc or not doc.get("chapters"):
            return None
        return doc["chapters"][0]

    # ── write paths: book-level ──────────────────────────────────────

    async def set_source_pdf(self, book_id: PyObjectId, asset: EmbeddedObject) -> bool:
        """Embed the source PDF metadata directly on the Book document."""
        result = await self._col.update_one(
            {"_id": self._oid(book_id)},
            {
                "$set": {
                    "source_pdf": asset.to_mongo(),
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        return result.matched_count > 0

    async def increment_total_pages(
        self, book_id: PyObjectId, delta: int
    ) -> bool:
        """Atomically add ``delta`` to ``Book.total_pages`` via ``$inc``.

        Used by the ingestion pipeline to accumulate page counts across
        all chapter PDFs.  No-op when ``delta == 0`` (idempotent re-run
        with the same page count).
        """
        if delta == 0:
            return True
        result = await self._col.update_one(
            {"_id": self._oid(book_id)},
            {"$inc": {"total_pages": delta}},
        )
        return result.matched_count > 0

    # ── write paths: chapter-level ───────────────────────────────────

    async def add_chapter(self, book_id: PyObjectId, chapter: EmbeddedChapter) -> bool:
        """Push a new embedded chapter onto the Book.chapters array.

        Atomic single-write operation.  Filters on ``chapter_no`` first
        so duplicates are silently skipped.
        """
        result = await self._col.update_one(
            {
                "_id": self._oid(book_id),
                "chapters.chapter_no": {"$ne": chapter.chapter_no},
            },
            {
                "$push": {"chapters": chapter.to_mongo()},
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
        )
        return result.matched_count > 0 and result.modified_count > 0

    async def add_chapters(
        self, book_id: PyObjectId, chapters: Sequence[EmbeddedChapter],
    ) -> bool:
        """Batch-append multiple chapters in a single ``$push + $each``.

        Used by catalog import to pre-create all of a book's chapters
        in one round trip instead of one-per-chapter.  Chapters whose
        ``chapter_no`` already exists are silently kept (the filter on
        ``chapters.chapter_no: {"$nin": [...]}`` prevents duplicates).
        """
        if not chapters:
            return True
        existing_nos = [c.chapter_no for c in chapters]
        result = await self._col.update_one(
            {
                "_id": self._oid(book_id),
                "chapters.chapter_no": {"$nin": existing_nos},
            },
            {
                "$push": {
                    "chapters": {"$each": [c.to_mongo() for c in chapters]},
                },
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
        )
        return result.matched_count > 0

    async def ensure_chapter(
        self,
        book_id: PyObjectId,
        chapter_no: int,
        title: str,
        page_start: int | None = None,
        page_end: int | None = None,
        summary: str | None = None,
        pdf_filename: str | None = None,
        chapter_code: str | None = None,
        preferred_llm: str | None = None,
        catalog_source: str | None = None,
    ) -> ObjectId:
        """Return the existing chapter_id, or insert a new embedded chapter."""
        existing = await self.find_chapter_by_no(book_id, chapter_no)
        if existing and existing.get("id"):
            return (
                existing["id"]
                if isinstance(existing["id"], ObjectId)
                else ObjectId(existing["id"])
            )

        chapter = EmbeddedChapter(
            chapter_no=chapter_no,
            title=title,
            summary=summary,
            page_start=page_start,
            page_end=page_end,
            pdf_filename=pdf_filename,
            chapter_code=chapter_code,
            preferred_llm=preferred_llm,
            catalog_source=catalog_source,
        )
        await self.add_chapter(book_id, chapter)
        return chapter.id

    async def update_chapter_page_end(
        self,
        book_id: PyObjectId,
        chapter_id: PyObjectId,
        page_end: int,
    ) -> bool:
        """Update a chapter's ``page_end`` field."""
        result = await self._col.update_one(
            {"_id": self._oid(book_id), "chapters.id": self._oid(chapter_id)},
            {
                "$set": {
                    "chapters.$.page_end": page_end,
                    "chapters.$.updated_at": datetime.now(timezone.utc),
                }
            },
        )
        if result.matched_count == 0:
            logger.error(
                "update_chapter_page_end NO MATCH",
                extra={
                    "book_id": str(book_id),
                    "chapter_id": str(chapter_id),
                    "page_end": page_end,
                },
            )
        return result.matched_count > 0 and result.modified_count > 0

    # ── write paths: chapter objects (page images) ────────────────────

    async def add_chapter_object(
        self,
        book_id: PyObjectId,
        chapter_id: PyObjectId,
        asset: EmbeddedObject,
    ) -> bool:
        """Push a single page-level object into ``chapter.objects[]``."""
        result = await self._col.update_one(
            {"_id": self._oid(book_id), "chapters.id": self._oid(chapter_id)},
            {
                "$push": {"chapters.$.objects": asset.to_mongo()},
                "$set": {"chapters.$.updated_at": datetime.now(timezone.utc)},
            },
        )
        return result.matched_count > 0 and result.modified_count > 0

    async def add_chapter_objects(
        self,
        book_id: PyObjectId,
        chapter_id: PyObjectId,
        assets: Sequence[EmbeddedObject],
    ) -> bool:
        """Batch-append multiple page objects in a single ``$push + $each``.

        This is the batched equivalent of :meth:`add_chapter_object` and
        the primary write path used by the ingestion pipeline — one
        round trip per chapter instead of one per page.
        """
        if not assets:
            return True
        result = await self._col.update_one(
            {"_id": self._oid(book_id), "chapters.id": self._oid(chapter_id)},
            {
                "$push": {
                    "chapters.$.objects": {
                        "$each": [a.to_mongo() for a in assets],
                    },
                },
                "$set": {"chapters.$.updated_at": datetime.now(timezone.utc)},
            },
        )
        return result.matched_count > 0 and result.modified_count > 0

    async def finalize_chapter_ingestion(
        self,
        book_id: PyObjectId,
        chapter_id: PyObjectId,
        processed_pages: int,
        page_end: int | None = None,
    ) -> bool:
        """Stamp ``processed_pages`` (and optionally ``page_end``) in one write.

        Replaces the previous pattern of calling
        :meth:`update_chapter_processed_pages` and
        :meth:`update_chapter_page_end` separately — one round trip
        instead of two.
        """
        set_payload: dict[str, Any] = {
            "chapters.$.processed_pages": processed_pages,
            "chapters.$.updated_at": datetime.now(timezone.utc),
        }
        if page_end is not None:
            set_payload["chapters.$.page_end"] = page_end
        result = await self._col.update_one(
            {"_id": self._oid(book_id), "chapters.id": self._oid(chapter_id)},
            {"$set": set_payload},
        )
        return result.matched_count > 0

    async def clear_chapter_objects(
        self,
        book_id: PyObjectId,
        chapter_id: PyObjectId,
    ) -> bool:
        """Empty the chapter's ``objects`` array and reset ``processed_pages``.

        Used at the start of chapter re-ingestion to prevent duplicate
        page images from accumulating on repeated runs.  Both fields are
        set in a single atomic write.
        """
        result = await self._col.update_one(
            {"_id": self._oid(book_id), "chapters.id": self._oid(chapter_id)},
            {
                "$set": {
                    "chapters.$.objects": [],
                    "chapters.$.processed_pages": 0,
                    "chapters.$.updated_at": datetime.now(timezone.utc),
                }
            },
        )
        return result.matched_count > 0

    async def update_chapter_pdf_ref(
        self,
        book_id: PyObjectId,
        chapter_id: PyObjectId,
        pdf_object_key: str,
        pdf_bucket_name: str,
        pdf_object_url: Optional[str],
        pdf_size_bytes: int,
    ) -> bool:
        """Store the full chapter PDF reference directly on the chapter.

        .. versionchanged:: v6
            ``pdf_object_url`` is now optional.  When ``None``, the
            ``pdf_object_url`` field on the chapter is unset (``$unset``)
            so new records do not carry a stale persistent URL.  When
            a string is passed (legacy callers), the field is ``$set``
            to that value for backward compatibility.
        """
        set_payload: dict[str, Any] = {
            "chapters.$.pdf_object_key": pdf_object_key,
            "chapters.$.pdf_bucket_name": pdf_bucket_name,
            "chapters.$.pdf_size_bytes": pdf_size_bytes,
            "chapters.$.updated_at": datetime.now(timezone.utc),
        }
        unset_payload: dict[str, Any] = {}
        if pdf_object_url is None:
            # v6: new uploads — clear any stale URL left from a
            # previous v5 write (re-ingestion of an existing chapter).
            unset_payload["chapters.$.pdf_object_url"] = ""
        else:
            # Legacy caller explicitly passed a URL — preserve it.
            set_payload["chapters.$.pdf_object_url"] = pdf_object_url

        update_doc: dict[str, Any] = {"$set": set_payload}
        if unset_payload:
            update_doc["$unset"] = unset_payload

        result = await self._col.update_one(
            {"_id": self._oid(book_id), "chapters.id": self._oid(chapter_id)},
            update_doc,
        )
        return result.matched_count > 0

    async def update_chapter_processed_pages(
        self,
        book_id: PyObjectId,
        chapter_id: PyObjectId,
        processed_pages: int,
    ) -> bool:
        """Update the ``processed_pages`` counter on the chapter.

        Kept for backwards compatibility — new code should prefer
        :meth:`finalize_chapter_ingestion` which stamps ``processed_pages``
        and ``page_end`` in a single write.
        """
        result = await self._col.update_one(
            {"_id": self._oid(book_id), "chapters.id": self._oid(chapter_id)},
            {"$set": {
                "chapters.$.processed_pages": processed_pages,
                "chapters.$.updated_at": datetime.now(timezone.utc),
            }},
        )
        return result.matched_count > 0
