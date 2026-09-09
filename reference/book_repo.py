from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from db.models.base import PyObjectId
from db.models.book import Book
from db.models.embedded import EmbeddedChapter, EmbeddedObject, EmbeddedOCRPage
from .base_mongo_repo import BaseMongoRepository


class BookRepository(BaseMongoRepository[Book]):
    collection_name = "BOOKS"
    model_class = Book

    # ── read paths ───────────────────────────────────────────────────

    async def find_by_class_and_subject(
        self, class_no: int, subject: str, edition: str | None = None
    ) -> Book | None:
        filter_: dict[str, Any] = {"class_no": class_no, "subject": subject}
        if edition is not None:
            filter_["edition"] = edition
        results = await self.find_many(filter_, limit=1)
        return results[0] if results else None

    async def find_by_class(self, class_no: int) -> list[Book]:
        return await self.find_many({"class_no": class_no}, limit=100)

    async def find_by_subject(self, subject: str) -> list[Book]:
        return await self.find_many({"subject": subject}, limit=100)

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

    async def find_chapter_by_id(
        self, book_id: PyObjectId, chapter_id: PyObjectId
    ) -> dict[str, Any] | None:
        doc = await self._col.find_one(
            {"_id": self._oid(book_id), "chapters.id": self._oid(chapter_id)},
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

    # ── write paths: chapter-level ───────────────────────────────────

    async def add_chapter(self, book_id: PyObjectId, chapter: EmbeddedChapter) -> bool:
        """Push a new embedded chapter onto the Book.chapters array.

        Atomic single-write operation. Uses `$addToSet` semantics by
        filtering on chapter_no first to avoid duplicates — if a chapter
        with the same chapter_no already exists, the push is a no-op
        because the update filter does not match.
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

    async def update_chapter_page_range(
        self,
        book_id: PyObjectId,
        chapter_id: PyObjectId,
        page_start: int | None = None,
        page_end: int | None = None,
        summary: str | None = None,
    ) -> bool:
        """Update lightweight chapter metadata in place.

        Uses the positional `$` operator to address the matched chapter.
        """
        set_payload: dict[str, Any] = {
            "chapters.$.updated_at": datetime.now(timezone.utc),
        }
        if page_start is not None:
            set_payload["chapters.$.page_start"] = page_start
        if page_end is not None:
            set_payload["chapters.$.page_end"] = page_end
        if summary is not None:
            set_payload["chapters.$.summary"] = summary

        result = await self._col.update_one(
            {"_id": self._oid(book_id), "chapters.id": self._oid(chapter_id)},
            {"$set": set_payload},
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
    ) -> ObjectId:
        """Return the existing chapter_id, or insert a new embedded chapter.

        Returns the ObjectId of the chapter (existing or newly created).
        """
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
        )
        await self.add_chapter(book_id, chapter)
        return chapter.id

    # ── write paths: chapter object metadata ─────────────────────────

    async def add_chapter_object(
        self,
        book_id: PyObjectId,
        chapter_id: PyObjectId,
        asset: EmbeddedObject,
    ) -> bool:
        """Push a page-image (or other chapter-scoped asset) into a chapter.

        Uses the positional `$` operator against `chapters.id` so the
        update is a single atomic write.
        """
        result = await self._col.update_one(
            {"_id": self._oid(book_id), "chapters.id": self._oid(chapter_id)},
            {
                "$push": {"chapters.$.objects": asset.to_mongo()},
                "$set": {"chapters.$.updated_at": datetime.now(timezone.utc)},
            },
        )
        return result.matched_count > 0 and result.modified_count > 0

    # ── write paths: chapter OCR pages ───────────────────────────────

    async def add_chapter_ocr_page(
        self,
        book_id: PyObjectId,
        chapter_id: PyObjectId,
        ocr_page: EmbeddedOCRPage,
    ) -> bool:
        """Push one OCR page into the matching chapter's `ocr_pages` array."""
        result = await self._col.update_one(
            {"_id": self._oid(book_id), "chapters.id": self._oid(chapter_id)},
            {
                "$push": {"chapters.$.ocr_pages": ocr_page.to_mongo()},
                "$set": {"chapters.$.updated_at": datetime.now(timezone.utc)},
            },
        )
        return result.matched_count > 0 and result.modified_count > 0

    async def add_chapter_ocr_pages(
        self,
        book_id: PyObjectId,
        chapter_id: PyObjectId,
        ocr_pages: list[EmbeddedOCRPage],
    ) -> bool:
        """Push multiple OCR pages in a single atomic write."""
        if not ocr_pages:
            return True
        result = await self._col.update_one(
            {"_id": self._oid(book_id), "chapters.id": self._oid(chapter_id)},
            {
                "$push": {
                    "chapters.$.ocr_pages": {"$each": [p.to_mongo() for p in ocr_pages]}
                },
                "$set": {"chapters.$.updated_at": datetime.now(timezone.utc)},
            },
        )
        return result.matched_count > 0 and result.modified_count > 0
