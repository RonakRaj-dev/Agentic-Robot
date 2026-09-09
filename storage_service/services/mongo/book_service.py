"""MongoDB-backed Book service — single orchestrator over the BOOKS collection.

All chapter and page-object mutations go through this service as
intent-revealing methods that translate to atomic ``$set`` / ``$push``
operations on the Book aggregate root.  Batch appends use ``$push`` with
``$each`` so a whole chapter's worth of page objects can be persisted
in one round trip instead of one-per-page.

Schema v3:
  * ``total_pages`` accumulates across all chapter PDFs.
  * Each chapter stores its full PDF reference directly
    (pdf_object_key, pdf_bucket_name, pdf_object_url, pdf_size_bytes).
  * Each page is stored as a PAGE_IMAGE ``EmbeddedObject`` in
    ``chapter.objects[]``.
  * ``processed_pages`` counter tracks processed page count per chapter.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from db.models.embedded import (
    EmbeddedObject,
    EmbeddedChapter,
    ObjectType,
)
from db.models.book import Book
from interfaces.book_service import IBookService
from repos.mongo.book_repo import BookRepository
from utils.oid_utils import to_oid, parse_storage_url


class MongoBookService(IBookService):
    """Concrete Book service backed by MongoDB."""

    def __init__(self, book_repo: Optional[BookRepository] = None) -> None:
        self._repo = book_repo or BookRepository()

    # ── book lifecycle ───────────────────────────────────────────────

    async def create_book(
        self,
        title: str,
        class_level: str,
        subject: str,
        language: str,
        board: str,
        metadata: Dict[str, Any],
        pdf_asset_id: str,
        total_pages: int,
    ) -> str:
        """Create a new Book document with an empty ``chapters`` array."""
        try:
            class_no = _safe_int_class_level(class_level)
            book = Book(
                class_no=class_no,
                subject=subject,
                title=title,
                total_pages=total_pages,
                board=board,
                metadata={
                    "language": language,
                    "pdf_asset_id": pdf_asset_id,
                    **(metadata or {}),
                },
            )
            inserted = await self._repo.insert(book)
            return str(inserted)
        except Exception as exc:
            raise _wrap("create_book", exc) from exc

    async def get_book(self, book_id: str) -> Optional[Book]:
        try:
            return await self._repo.find_by_id(book_id)
        except Exception as exc:
            raise _wrap("get_book", exc) from exc

    async def get_book_by_code(
        self,
        class_no: int,
        subject: str,
        title: Optional[str] = None,
        board: Optional[str] = None,
    ) -> Optional[str]:
        """Find a book by its unique identity. Returns book_id or None."""
        try:
            book = await self._repo.find_by_identity(
                class_no=class_no,
                subject=subject,
                title=title,
                board=board,
            )
            return str(book.id) if book else None
        except Exception as exc:
            raise _wrap("get_book_by_code", exc) from exc

    async def update_book_status(
        self,
        book_id: str,
        status: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        try:
            updates: Dict[str, Any] = {"ingestion_status": status}
            if metadata:
                updates.setdefault("metadata", {}).update(metadata)
            return await self._repo.update(book_id, updates)
        except Exception as exc:
            raise _wrap("update_book_status", exc) from exc

    async def update_book_total_pages(
        self,
        book_id: str,
        total_pages: int,
    ) -> bool:
        """Adjust ``book.total_pages`` by ``total_pages`` (delta, can be negative)."""
        try:
            return await self._repo.increment_total_pages(
                to_oid(book_id), total_pages,
            )
        except Exception as exc:
            raise _wrap("update_book_total_pages", exc) from exc

    # ── source PDF ───────────────────────────────────────────────────

    async def attach_source_pdf(
        self,
        book_id: str,
        file_path: Path,
        metadata: Dict[str, Any],
        storage_url: Optional[str] = None,
        bucket_name: Optional[str] = None,
        object_key: Optional[str] = None,
    ) -> str:
        """Embed source-PDF metadata directly on the Book document.

        .. versionchanged:: v6
            Prefers structured ``bucket_name`` + ``object_key``.  Falls
            back to parsing ``storage_url`` via ``parse_storage_url``
            when the structured fields are not provided.  The legacy
            ``object_url`` field on the resulting :class:`EmbeddedObject`
            is left as ``None`` for new uploads — persistent URLs are
            no longer stored.

        .. versionchanged:: v7
            Presigned URL generation has been removed.  Callers that
            need an access URL must use
            :meth:`IStorageService.get_public_url` with the structured
            ``bucket_name`` + ``object_key`` fields.
        """
        try:
            # Resolve structured (bucket, key) — prefer explicit args,
            # fall back to parsing the legacy URL.
            if not (bucket_name and object_key) and storage_url:
                parsed_bucket, parsed_key = parse_storage_url(storage_url)
                bucket_name = bucket_name or parsed_bucket
                object_key = object_key or parsed_key

            if not (bucket_name and object_key):
                raise ValueError(
                    "attach_source_pdf requires either bucket_name + "
                    "object_key, or a parseable storage_url"
                )

            asset = EmbeddedObject(
                object_type=ObjectType.SOURCE_PDF,
                object_key=object_key,
                bucket_name=bucket_name,
                object_url=None,  # v6: no persistent URL stored
                mime_type="application/pdf",
                size_bytes=int(metadata.get("file_size", 0) or 0),
                metadata={
                    "original_filename": metadata.get("original_filename"),
                    "board": metadata.get("board"),
                    "class_level": metadata.get("class_level"),
                    "subject": metadata.get("subject"),
                    "source": "ingestion_pipeline",
                },
            )
            await self._repo.set_source_pdf(to_oid(book_id), asset)
            return str(asset.id)
        except Exception as exc:
            raise _wrap("attach_source_pdf", exc) from exc

    # ── chapters ────────────────────────────────────────────────────

    async def add_chapter(
        self,
        book_id: str,
        chapter_no: int,
        title: str,
        page_start: Optional[int] = None,
        page_end: Optional[int] = None,
        summary: Optional[str] = None,
        pdf_filename: Optional[str] = None,
        chapter_code: Optional[str] = None,
        preferred_llm: Optional[str] = None,
        catalog_source: Optional[str] = None,
    ) -> str:
        """Return the existing chapter_id, or push a new embedded chapter."""
        try:
            chapter_id = await self._repo.ensure_chapter(
                to_oid(book_id),
                chapter_no,
                title,
                page_start=page_start,
                page_end=page_end,
                summary=summary,
                pdf_filename=pdf_filename,
                chapter_code=chapter_code,
                preferred_llm=preferred_llm,
                catalog_source=catalog_source,
            )
            return str(chapter_id)
        except Exception as exc:
            raise _wrap("add_chapter", exc) from exc

    async def add_chapters(
        self,
        book_id: str,
        chapters: Sequence[Dict[str, Any]],
    ) -> bool:
        """Batch-append multiple chapters in a single ``$push + $each``."""
        try:
            embedded = [
                EmbeddedChapter(
                    chapter_no=c["chapter_no"],
                    title=c["title"],
                    summary=c.get("summary"),
                    page_start=c.get("page_start"),
                    page_end=c.get("page_end"),
                    pdf_filename=c.get("pdf_filename"),
                    chapter_code=c.get("chapter_code"),
                    preferred_llm=c.get("preferred_llm"),
                    catalog_source=c.get("catalog_source"),
                )
                for c in chapters
            ]
            return await self._repo.add_chapters(to_oid(book_id), embedded)
        except Exception as exc:
            raise _wrap("add_chapters", exc) from exc

    async def get_chapter(
        self,
        book_id: str,
        chapter_no: int,
    ) -> Optional[Dict[str, Any]]:
        """Return a single chapter sub-document by chapter_no, or None."""
        try:
            return await self._repo.find_chapter_by_no(
                to_oid(book_id), chapter_no,
            )
        except Exception as exc:
            raise _wrap("get_chapter", exc) from exc

    async def find_chapter_by_pdf_filename(
        self,
        pdf_filename: str,
    ) -> Optional[Dict[str, str]]:
        """Look up a chapter by its pdf_filename across all books."""
        try:
            result = await self._repo.find_chapter_by_pdf_filename(pdf_filename)
            if result is None:
                return None
            return {
                "book_id": str(result["book_id"]),
                "chapter_no": str(result.get("chapter_no", "")),
            }
        except Exception as exc:
            raise _wrap("find_chapter_by_pdf_filename", exc) from exc

    async def update_chapter_pdf_ref(
        self,
        book_id: str,
        chapter_id: str,
        pdf_object_key: str,
        pdf_bucket_name: str,
        pdf_size_bytes: int,
        pdf_object_url: Optional[str] = None,
    ) -> bool:
        """Store the full chapter PDF reference directly on the chapter.

        .. versionchanged:: v6
            ``pdf_object_url`` is now optional and defaults to ``None``.
            New callers SHOULD NOT pass a URL — persistent URLs are no
            longer stored.

        .. versionchanged:: v7
            Presigned URL generation has been removed.  Callers that
            need an access URL must use
            :meth:`IStorageService.get_public_url` with
            ``pdf_bucket_name`` + ``pdf_object_key``.
        """
        try:
            return await self._repo.update_chapter_pdf_ref(
                to_oid(book_id), to_oid(chapter_id),
                pdf_object_key, pdf_bucket_name, pdf_object_url, pdf_size_bytes,
            )
        except Exception as exc:
            raise _wrap("update_chapter_pdf_ref", exc) from exc

    async def finalize_chapter_ingestion(
        self,
        book_id: str,
        chapter_id: str,
        processed_pages: int,
        page_end: Optional[int] = None,
    ) -> bool:
        """Stamp ``processed_pages`` (and optionally ``page_end``) in one write."""
        try:
            return await self._repo.finalize_chapter_ingestion(
                to_oid(book_id), to_oid(chapter_id),
                processed_pages, page_end=page_end,
            )
        except Exception as exc:
            raise _wrap("finalize_chapter_ingestion", exc) from exc

    async def clear_chapter_objects(
        self,
        book_id: str,
        chapter_id: str,
    ) -> bool:
        """Empty the chapter's ``objects`` array (used on re-ingestion)."""
        try:
            return await self._repo.clear_chapter_objects(
                to_oid(book_id), to_oid(chapter_id),
            )
        except Exception as exc:
            raise _wrap("clear_chapter_objects", exc) from exc

    # ── chapter objects (page images) ────────────────────────────────

    async def append_page_object(
        self,
        book_id: str,
        chapter_id: str,
        page_object: EmbeddedObject,
    ) -> bool:
        """Push a single page-level EmbeddedObject into ``chapter.objects[]``."""
        try:
            return await self._repo.add_chapter_object(
                to_oid(book_id), to_oid(chapter_id), page_object
            )
        except Exception as exc:
            raise _wrap(
                "append_page_object",
                exc,
                page_no=page_object.page_no,
            ) from exc

    async def append_page_objects(
        self,
        book_id: str,
        chapter_id: str,
        page_objects: Sequence[EmbeddedObject],
    ) -> bool:
        """Batch-append multiple page objects in a single ``$push + $each``."""
        try:
            return await self._repo.add_chapter_objects(
                to_oid(book_id), to_oid(chapter_id), page_objects,
            )
        except Exception as exc:
            first_page_no = next(
                (po.page_no for po in page_objects if po.page_no is not None),
                None,
            )
            raise _wrap(
                "append_page_objects",
                exc,
                page_no=first_page_no,
            ) from exc

    async def append_processed_pages(
        self,
        book_id: str,
        chapter_id: str,
        pages: Sequence[Dict[str, Any]],
    ) -> List[str]:
        """Batch-append multiple processed pages as PAGE_IMAGE objects.

        Builds the ``EmbeddedObject`` instances internally and persists
        them in a single batched write.  Returns the list of new
        object_ids as strings.

        .. versionchanged:: v6
            The ``object_url`` key in each page dict is now optional
            and defaults to ``None``.  New callers SHOULD NOT include
            it — persistent URLs are no longer stored.

        .. versionchanged:: v7
            Presigned URL generation has been removed.  Callers that
            need an access URL must use
            :meth:`IStorageService.get_public_url` with the
            ``bucket_name`` + ``object_key`` fields stored on each
            page image.
        """
        page_objects: List[EmbeddedObject] = []
        for p in pages:
            page_objects.append(EmbeddedObject(
                object_type=ObjectType.PAGE_IMAGE,
                object_key=p["object_key"],
                bucket_name=p["bucket_name"],
                object_url=p.get("object_url"),  # v6: usually None
                page_no=p["page_no"],
                mime_type=p.get("mime_type", "image/png"),
                size_bytes=p["size_bytes"],
                metadata={
                    "plain_text": p.get("plain_text", ""),
                    "word_count": int(p.get("word_count", 0)),
                    "token_count": int(p.get("token_count", 0)),
                    "extraction_method": p.get("extraction_method", "pymupdf"),
                },
            ))
        if not page_objects:
            return []
        ok = await self.append_page_objects(
            book_id=book_id,
            chapter_id=chapter_id,
            page_objects=page_objects,
        )
        if not ok:
            from core.exceptions import MongoWriteError
            raise MongoWriteError(
                "append_processed_pages failed",
                collection="BOOKS",
            )
        return [str(po.id) for po in page_objects]


# ── private helpers ────────────────────────────────────────────────────


def _safe_int_class_level(class_level: Any) -> int:
    """Coerce class_level to int; defaults to 0 on failure."""
    try:
        return int(class_level)
    except (TypeError, ValueError):
        import re
        if isinstance(class_level, str):
            match = re.search(r'\d+', class_level)
            if match:
                return int(match.group(0))
        return 0


def _wrap(stage: str, exc: Exception, page_no: Optional[int] = None):
    """Wrap an unexpected service-layer exception in a MongoWriteError."""
    from core.exceptions import MongoWriteError
    return MongoWriteError(
        f"{stage} failed: {exc}", collection="BOOKS", page_no=page_no,
    )
