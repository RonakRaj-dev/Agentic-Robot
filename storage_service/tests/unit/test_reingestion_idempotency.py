"""Unit tests: chapter re-ingestion idempotency.

Verifies that re-running ``ingest_chapter`` on a chapter that has
already been processed:
  * does not duplicate PAGE_IMAGE objects in ``chapter.objects[]``
  * does not double-count the book's ``total_pages``
  * resets ``processed_pages`` to the new page count
"""
from __future__ import annotations

import logging

import pytest

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
pytestmark = pytest.mark.asyncio


async def _build_chaptered_book(pipeline, services, sample_pdf_path):
    """Run one full catalog-style ingest cycle and return (book_id, chapter_id)."""
    books = services["books"]

    # Create a Book with an embedded chapter (mirrors catalog import).
    book_id = await books.create_book(
        title="Re-Ingestion Test",
        class_level="8",
        subject="Science",
        language="en",
        board="NCERT",
        metadata={"catalog_source": "test"},
        pdf_asset_id="",
        total_pages=0,
    )
    chapter_id = await books.add_chapter(
        book_id=book_id,
        chapter_no=1,
        title="Test Chapter",
        pdf_filename="test.pdf",
    )
    await pipeline.ingest_chapter(
        pdf_path=sample_pdf_path,
        book_id=book_id,
        chapter_no=1,
    )
    return book_id, chapter_id


async def test_re_ingestion_does_not_duplicate_page_objects(
    in_memory_pipeline, sample_pdf_path
):
    pipeline, services = in_memory_pipeline
    book_id, chapter_id = await _build_chaptered_book(pipeline, services, sample_pdf_path)

    # First run: 3 page objects.
    book = await services["books"].get_book(book_id)
    chapter = next(c for c in book["chapters"] if c["id"] == chapter_id)
    assert len(chapter["objects"]) == 3
    assert chapter["processed_pages"] == 3
    assert book["total_pages"] == 3

    # Second run on the same chapter — should REPLACE, not duplicate.
    await pipeline.ingest_chapter(
        pdf_path=sample_pdf_path,
        book_id=book_id,
        chapter_no=1,
    )

    book = await services["books"].get_book(book_id)
    chapter = next(c for c in book["chapters"] if c["id"] == chapter_id)
    assert len(chapter["objects"]) == 3, (
        f"Re-ingestion should not duplicate page objects, got {len(chapter['objects'])}"
    )
    assert chapter["processed_pages"] == 3


async def test_re_ingestion_does_not_double_count_total_pages(
    in_memory_pipeline, sample_pdf_path
):
    """Re-running ``ingest_chapter`` must not increment ``book.total_pages`` again."""
    pipeline, services = in_memory_pipeline
    book_id, _ = await _build_chaptered_book(pipeline, services, sample_pdf_path)

    book = await services["books"].get_book(book_id)
    assert book["total_pages"] == 3

    await pipeline.ingest_chapter(
        pdf_path=sample_pdf_path,
        book_id=book_id,
        chapter_no=1,
    )

    book = await services["books"].get_book(book_id)
    assert book["total_pages"] == 3, (
        f"Re-ingestion should not double-count total_pages, got {book['total_pages']}"
    )


async def test_clear_chapter_objects_resets_state(
    in_memory_pipeline, sample_pdf_path
):
    """Direct test of the new ``clear_chapter_objects`` service method."""
    pipeline, services = in_memory_pipeline
    book_id, chapter_id = await _build_chaptered_book(pipeline, services, sample_pdf_path)

    book = await services["books"].get_book(book_id)
    chapter = next(c for c in book["chapters"] if c["id"] == chapter_id)
    assert len(chapter["objects"]) == 3
    assert chapter["processed_pages"] == 3

    ok = await services["books"].clear_chapter_objects(
        book_id=book_id, chapter_id=chapter_id,
    )
    assert ok is True

    book = await services["books"].get_book(book_id)
    chapter = next(c for c in book["chapters"] if c["id"] == chapter_id)
    assert chapter["objects"] == []
    assert chapter["processed_pages"] == 0


async def test_clear_chapter_objects_returns_false_for_unknown_chapter(
    in_memory_pipeline, sample_pdf_path
):
    """``clear_chapter_objects`` should return False when the chapter_id is unknown."""
    pipeline, services = in_memory_pipeline
    book_id, _ = await _build_chaptered_book(pipeline, services, sample_pdf_path)

    ok = await services["books"].clear_chapter_objects(
        book_id=book_id, chapter_id="does-not-exist",
    )
    assert ok is False
