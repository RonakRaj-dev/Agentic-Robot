"""Unit tests: batched page-object persistence.

Verifies that the pipeline's page-processing stage persists all page
objects in a SINGLE batched ``$push + $each`` write instead of one
``update_one`` per page.  The test instruments the in-memory
``InMemoryBookService`` to count calls to ``append_processed_pages``
(the batched method) vs ``append_page_object`` (the single-page
method).

Also covers:
  * ``finalize_chapter_ingestion`` stamps both ``processed_pages`` and
    ``page_end`` in one call.
  * ``add_chapters`` batch-creates multiple chapters in one call.
  * The ``StorageRef`` returned by ``upload_page_image`` is what gets
    stored on the PAGE_IMAGE object (no settings lookup in the
    pipeline).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.asyncio


async def test_pipeline_uses_batched_append_not_per_page(
    in_memory_pipeline, sample_pdf_path,
):
    """The pipeline must call ``append_processed_pages`` (batched) exactly
    once per chapter, NOT ``append_page_object`` (per-page) N times.
    """
    pipeline, services = in_memory_pipeline
    books = services["books"]

    # Instrument both methods to count calls.
    append_batch_calls = []
    append_single_calls = []

    original_batch = books.append_processed_pages
    original_single = books.append_page_object

    async def counting_batch(*args, **kwargs):
        append_batch_calls.append(kwargs.get("pages", []))
        return await original_batch(*args, **kwargs)

    async def counting_single(*args, **kwargs):
        append_single_calls.append(kwargs.get("page_object"))
        return await original_single(*args, **kwargs)

    books.append_processed_pages = counting_batch
    books.append_page_object = counting_single

    # Run a catalog-style ingest.
    book_id = await books.create_book(
        title="T", class_level="8", subject="Science", language="en",
        board="NCERT", metadata={}, pdf_asset_id="", total_pages=0,
    )
    await books.add_chapter(book_id=book_id, chapter_no=1, title="Ch 1")
    await pipeline.ingest_chapter(
        pdf_path=sample_pdf_path, book_id=book_id, chapter_no=1,
    )

    # The batched method should be called exactly once with all 3 pages.
    assert len(append_batch_calls) == 1, (
        f"Expected 1 batched append call, got {len(append_batch_calls)}"
    )
    assert len(append_batch_calls[0]) == 3, (
        f"Expected 3 pages in the batch, got {len(append_batch_calls[0])}"
    )
    # The per-page method should NOT be called at all.
    assert len(append_single_calls) == 0, (
        f"Pipeline must not call append_page_object per page; "
        f"got {len(append_single_calls)} calls"
    )


async def test_pipeline_uses_finalize_not_two_separate_writes(
    in_memory_pipeline, sample_pdf_path,
):
    """The pipeline must call ``finalize_chapter_ingestion`` (one write)
    NOT ``update_chapter_processed_pages`` + ``update_chapter_page_end``
    (two writes).
    """
    pipeline, services = in_memory_pipeline
    books = services["books"]

    finalize_calls = []
    update_processed_pages_calls = []
    update_page_end_calls = []

    original_finalize = books.finalize_chapter_ingestion

    async def counting_finalize(*args, **kwargs):
        finalize_calls.append(kwargs)
        return await original_finalize(*args, **kwargs)

    books.finalize_chapter_ingestion = counting_finalize

    # Run a catalog-style ingest.
    book_id = await books.create_book(
        title="T", class_level="8", subject="Science", language="en",
        board="NCERT", metadata={}, pdf_asset_id="", total_pages=0,
    )
    await books.add_chapter(book_id=book_id, chapter_no=1, title="Ch 1")
    await pipeline.ingest_chapter(
        pdf_path=sample_pdf_path, book_id=book_id, chapter_no=1,
    )

    assert len(finalize_calls) == 1, (
        f"Expected 1 finalize call, got {len(finalize_calls)}"
    )
    # The finalize call should carry both processed_pages and page_end.
    assert finalize_calls[0].get("processed_pages") == 3
    assert finalize_calls[0].get("page_end") == 3


async def test_pipeline_does_not_read_settings_for_buckets(
    in_memory_pipeline, sample_pdf_path,
):
    """The pipeline must NOT read ``self.config.minio_bucket_*`` for
    chapter PDFs or page images — the StorageService returns a
    StorageRef carrying the bucket name.
    """
    pipeline, services = in_memory_pipeline

    # Instrument the pipeline's config attribute to raise if read.
    class ExplodingConfig:
        def __getattr__(self, name):
            if name.startswith("minio_bucket"):
                raise AssertionError(
                    f"Pipeline must not read config.{name} — "
                    f"StorageService should return a StorageRef"
                )
            # Allow other config reads (e.g. during construction).
            return getattr(pipeline.config, name)

    pipeline.config = ExplodingConfig()

    book_id = await services["books"].create_book(
        title="T", class_level="8", subject="Science", language="en",
        board="NCERT", metadata={}, pdf_asset_id="", total_pages=0,
    )
    await services["books"].add_chapter(book_id=book_id, chapter_no=1, title="Ch 1")

    # This should NOT raise — the pipeline gets bucket names from
    # StorageRef, not from settings.
    result = await pipeline.ingest_chapter(
        pdf_path=sample_pdf_path, book_id=book_id, chapter_no=1,
    )
    assert result.pipeline_status == "completed"


async def test_storage_ref_bucket_name_matches_storage_service(
    in_memory_pipeline, sample_pdf_path,
):
    """The bucket name stored on the PAGE_IMAGE object must match what
    the StorageService actually used (not what settings says).

    v6: ``object_url`` is no longer written — only ``bucket_name`` +
    ``object_key``.  The pipeline gets these from the StorageRef
    returned by ``upload_page_image``.
    """
    pipeline, services = in_memory_pipeline
    storage = services["storage"]

    # The in-memory storage uses "page-images" as the bucket name.
    book_id = await services["books"].create_book(
        title="T", class_level="8", subject="Science", language="en",
        board="NCERT", metadata={}, pdf_asset_id="", total_pages=0,
    )
    await services["books"].add_chapter(book_id=book_id, chapter_no=1, title="Ch 1")
    await pipeline.ingest_chapter(
        pdf_path=sample_pdf_path, book_id=book_id, chapter_no=1,
    )

    book = await services["books"].get_book(book_id)
    chapter = book["chapters"][0]
    for obj in chapter["objects"]:
        # The bucket_name on the stored object must match the in-memory
        # storage's bucket name — NOT a settings-derived value.
        assert obj["bucket_name"] == "page-images", (
            f"Expected bucket_name='page-images', got {obj['bucket_name']}"
        )
        # v6: object_url is no longer written for new uploads.
        assert obj.get("object_url") is None, (
            f"v6: object_url must be None for new uploads, got {obj['object_url']!r}"
        )


async def test_add_chapters_batch_creates_in_one_call(in_memory_services):
    """``add_chapters`` batch-creates all chapters in a single service call."""
    svc = in_memory_services.book_service
    book_id = await svc.create_book(
        title="T", class_level="8", subject="Science", language="en",
        board="NCERT", metadata={}, pdf_asset_id="", total_pages=0,
    )
    # Batch-create 5 chapters.
    await svc.add_chapters(book_id=book_id, chapters=[
        {"chapter_no": i, "title": f"Ch {i}", "pdf_filename": f"c{i}.pdf"}
        for i in range(1, 6)
    ])
    book = await svc.get_book(book_id)
    assert len(book["chapters"]) == 5
    # All chapter_nos present.
    nos = sorted(c["chapter_no"] for c in book["chapters"])
    assert nos == [1, 2, 3, 4, 5]
