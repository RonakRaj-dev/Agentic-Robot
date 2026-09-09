"""Book service interface.

BOOKS is the aggregate root.  All chapter and chapter-object mutations
go through this service as intent-revealing methods that translate to
atomic ``$set`` / ``$push`` operations.  No component outside this
service updates embedded chapter data directly.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional, Sequence


class IBookService(ABC):
    """Single service over the Book aggregate root."""

    # ── book lifecycle ───────────────────────────────────────────────

    @abstractmethod
    async def create_book(
        self,
        title: str,
        class_level: str,
        subject: str,
        language: str,
        board: str,
        metadata: dict[str, Any],
        pdf_asset_id: str,
        total_pages: int,
    ) -> str:
        """Create a new Book document with an empty ``chapters`` array.

        Returns the new book_id.
        """
        ...

    @abstractmethod
    async def get_book(self, book_id: str) -> Any:
        """Return the Book document (Pydantic model or dict in mocks)."""
        ...

    @abstractmethod
    async def get_book_by_code(
        self,
        class_no: int,
        subject: str,
        title: Optional[str] = None,
        board: Optional[str] = None,
    ) -> Optional[str]:
        """Find a book by its unique identity (class + subject + title + board).

        Returns the book_id if found, or None.  This is the idempotent
        lookup used during catalog import.
        """
        ...

    @abstractmethod
    async def update_book_status(
        self,
        book_id: str,
        status: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        ...

    @abstractmethod
    async def update_book_total_pages(
        self,
        book_id: str,
        total_pages: int,
    ) -> bool:
        """Adjust the book's ``total_pages`` by ``total_pages`` (delta).

        ``total_pages`` represents the total number of pages across ALL
        chapter PDFs in the book.  Pass a positive delta when adding
        pages, a negative delta when re-ingesting a chapter with fewer
        pages, and 0 for a no-op.
        """
        ...

    # ── source PDF ───────────────────────────────────────────────────

    @abstractmethod
    async def attach_source_pdf(
        self,
        book_id: str,
        file_path: Path,
        metadata: dict[str, Any],
        storage_url: Optional[str] = None,
        bucket_name: Optional[str] = None,
        object_key: Optional[str] = None,
    ) -> str:
        """Embed source-PDF metadata directly on the Book document.

        .. versionchanged:: v6
            Callers should now pass ``bucket_name`` + ``object_key``
            instead of ``storage_url``.  ``storage_url`` is retained
            for backward compatibility — when provided, it is parsed
            via :func:`utils.oid_utils.parse_storage_url` to derive
            ``bucket_name`` + ``object_key``.  When both are provided,
            the structured fields take precedence.

        .. versionchanged:: v7
            Presigned URL generation has been removed.  Callers that
            need an access URL must use
            :meth:`IStorageService.get_public_url` with the
            structured ``bucket_name`` + ``object_key`` fields.
        """
        ...

    # ── chapters ────────────────────────────────────────────────────

    @abstractmethod
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
        """Push a new embedded chapter onto ``book.chapters[]``.

        Idempotent: if a chapter with the same ``chapter_no`` already
        exists, returns its id without creating a duplicate.
        """
        ...

    @abstractmethod
    async def add_chapters(
        self,
        book_id: str,
        chapters: Sequence[dict[str, Any]],
    ) -> bool:
        """Batch-append multiple chapters in a single ``$push + $each``.

        Each dict in ``chapters`` carries the same fields as
        :meth:`add_chapter`'s kwargs (``chapter_no``, ``title``,
        ``pdf_filename``, etc.).  Used by catalog import to pre-create
        all of a book's chapters in one round trip.
        """
        ...

    @abstractmethod
    async def get_chapter(
        self,
        book_id: str,
        chapter_no: int,
    ) -> Optional[dict[str, Any]]:
        """Return a single chapter sub-document by chapter_no, or None."""
        ...

    @abstractmethod
    async def find_chapter_by_pdf_filename(
        self,
        pdf_filename: str,
    ) -> Optional[dict[str, str]]:
        """Look up a chapter by its pdf_filename across all books.

        Returns ``{"book_id": ..., "chapter_no": ...}`` if found, or None.
        """
        ...

    @abstractmethod
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
            New callers MUST NOT pass a URL — persistent URLs are no
            longer stored.  The parameter is kept in the signature for
            backward compatibility with code that has not been
            migrated yet.  When ``None``, the ``pdf_object_url`` field
            on the chapter document is set to ``None`` (or unset),
            which is the correct v6 behaviour.

        .. versionchanged:: v7
            Presigned URL generation has been removed.  Callers that
            need an access URL must use
            :meth:`IStorageService.get_public_url` with
            ``pdf_bucket_name`` + ``pdf_object_key``.
        """
        ...

    @abstractmethod
    async def finalize_chapter_ingestion(
        self,
        book_id: str,
        chapter_id: str,
        processed_pages: int,
        page_end: Optional[int] = None,
    ) -> bool:
        """Stamp ``processed_pages`` (and optionally ``page_end``) in one write.

        Replaces the previous pattern of calling
        :meth:`update_chapter_processed_pages` and
        :meth:`update_chapter_page_end` separately — one round trip
        instead of two.
        """
        ...

    @abstractmethod
    async def clear_chapter_objects(
        self,
        book_id: str,
        chapter_id: str,
    ) -> bool:
        """Empty the chapter's ``objects[]`` array (used on re-ingestion)."""
        ...

    # ── chapter objects (page images) ────────────────────────────────

    @abstractmethod
    async def append_page_object(
        self,
        book_id: str,
        chapter_id: str,
        page_object: Any,
    ) -> bool:
        """Push a single page-level EmbeddedObject into ``chapter.objects[]``."""
        ...

    @abstractmethod
    async def append_page_objects(
        self,
        book_id: str,
        chapter_id: str,
        page_objects: Sequence[Any],
    ) -> bool:
        """Batch-append multiple page objects in a single ``$push + $each``.

        This is the batched equivalent of :meth:`append_page_object` and
        the primary write path used by the ingestion pipeline — one
        round trip per chapter instead of one per page.
        """
        ...

    @abstractmethod
    async def append_processed_pages(
        self,
        book_id: str,
        chapter_id: str,
        pages: Sequence[dict[str, Any]],
    ) -> list[str]:
        """Batch-append multiple processed pages as PAGE_IMAGE objects.

        Each dict in ``pages`` carries the per-page fields (``page_no``,
        ``plain_text``, ``word_count``, ``token_count``,
        ``extraction_method``, ``object_key``, ``bucket_name``,
        ``size_bytes``, ``mime_type``).  Builds the ``EmbeddedObject``
        instances internally and persists them in a single batched
        write.  Returns the list of new object_ids.

        .. versionchanged:: v6
            The ``object_url`` key in each page dict is now optional
            and defaults to ``None``.  New callers SHOULD NOT include
            it — persistent URLs are no longer stored.  The key is
            still accepted for backward compatibility with code that
            has not been migrated yet.

        .. versionchanged:: v7
            Presigned URL generation has been removed.  Callers that
            need an access URL must use
            :meth:`IStorageService.get_public_url` with the
            ``bucket_name`` + ``object_key`` fields stored on each
            page image.
        """
        ...

    async def append_processed_page(
        self,
        book_id: str,
        chapter_id: str,
        page_no: int,
        plain_text: str,
        word_count: int,
        token_count: int,
        extraction_method: str,
        object_key: str,
        bucket_name: str,
        size_bytes: int,
        mime_type: str = "image/png",
        object_url: Optional[str] = None,
    ) -> str:
        """Append a single processed page as a PAGE_IMAGE object.

        Convenience wrapper around :meth:`append_processed_pages` for
        the single-page case.  Returns the new object_id as a string.

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
        ids = await self.append_processed_pages(
            book_id=book_id,
            chapter_id=chapter_id,
            pages=[{
                "page_no": page_no,
                "plain_text": plain_text,
                "word_count": word_count,
                "token_count": token_count,
                "extraction_method": extraction_method,
                "object_key": object_key,
                "bucket_name": bucket_name,
                "object_url": object_url,
                "size_bytes": size_bytes,
                "mime_type": mime_type,
            }],
        )
        return ids[0] if ids else ""
