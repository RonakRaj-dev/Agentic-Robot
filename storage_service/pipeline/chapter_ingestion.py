"""Chapter ingestion — upload chapter PDF + drive page processing.

This module is the single home for the chapter-level ingestion logic
that used to live inside ``IngestionPipeline._upload_chapter_pdf`` and
the first half of ``IngestionPipeline.ingest_chapter``.  Splitting it
out lets the orchestrator (``IngestionPipeline``) stay thin and makes
the reingestion-idempotency strategy explicit:

  1. Look up the chapter_id and previous ``processed_pages`` via
     :func:`lookup_chapter_for_ingest` (fetches the book, then walks
     chapters via the shared book-walking helper).
  2. Upload the chapter PDF via ``storage.upload_pdf`` (returns a
     :class:`StorageRef` — no settings lookup needed).
  3. Save the PDF reference on the chapter via
     ``books.update_chapter_pdf_ref``.
  4. The caller is responsible for adjusting ``book.total_pages`` by
     the delta and clearing existing page objects — see
     :class:`IngestionPipeline.ingest_chapter`.
"""
from __future__ import annotations

import logging
from pathlib import Path

from interfaces.book_service import IBookService
from interfaces.storage_service import IStorageService
from pipeline.book_walking import lookup_chapter_for_ingest

logger = logging.getLogger(__name__)


async def upload_chapter_pdf_and_attach(
    pdf_path: Path,
    book_id: str,
    chapter_no: int,
    books: IBookService,
    storage: IStorageService,
) -> tuple[str, int]:
    """Upload the chapter PDF and save its reference on the chapter.

    Returns ``(chapter_id, previous_processed_pages)`` so the caller
    can compute the correct ``total_pages`` delta and decide whether
    to call ``clear_chapter_objects``.
    """
    # Look up the chapter_id (and previous processed_pages) for this
    # chapter_no.  ``get_book`` is on the IBookService interface and
    # returns either a Book model (Mongo) or a plain dict (mock) —
    # ``lookup_chapter_for_ingest`` normalises both.
    book = await books.get_book(book_id)
    chapter_id, previous_processed_pages = lookup_chapter_for_ingest(
        book, book_id, chapter_no,
    )

    # Upload the chapter PDF via the StorageService business operation.
    # The bucket name and object-key convention are encapsulated inside
    # ``upload_pdf`` — the pipeline never touches settings.
    #
    # v7: ``ref`` carries ``(bucket_name, object_key)`` only — no URL
    # is stored.  The chapter PDF reference is persisted as
    # ``(pdf_bucket_name, pdf_object_key)`` on the chapter document.
    # Callers that need an access URL request one on demand via
    # ``storage.get_public_url(ref.bucket_name, ref.object_key)``.
    ref = await storage.upload_pdf(
        book_id=book_id,
        chapter_no=chapter_no,
        file_path=pdf_path,
    )
    pdf_size = pdf_path.stat().st_size

    # Save the PDF reference directly on the chapter.
    await books.update_chapter_pdf_ref(
        book_id=book_id,
        chapter_id=chapter_id,
        pdf_object_key=ref.object_key,
        pdf_bucket_name=ref.bucket_name,
        pdf_size_bytes=pdf_size,
        # v7: deliberately NOT passing pdf_object_url — persistent URLs
        # are no longer stored.  Callers that need an access URL must
        # request one via
        # ``storage.get_public_url(ref.bucket_name, ref.object_key)``.
    )

    return chapter_id, previous_processed_pages
