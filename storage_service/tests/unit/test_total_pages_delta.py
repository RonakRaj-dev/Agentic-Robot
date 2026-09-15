"""Unit tests: ``update_book_total_pages`` delta semantics.

Verifies that ``update_book_total_pages`` correctly applies the
*delta* — including negative deltas used when re-ingesting a chapter
with fewer pages than before.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_total_pages_increments_by_positive_delta(in_memory_pipeline):
    _, services = in_memory_pipeline
    book_id = await services["books"].create_book(
        title="Delta Test",
        class_level="8",
        subject="Science",
        language="en",
        board="NCERT",
        metadata={},
        pdf_asset_id="",
        total_pages=0,
    )

    ok = await services["books"].update_book_total_pages(book_id, 10)
    assert ok is True
    book = await services["books"].get_book(book_id)
    assert book["total_pages"] == 10

    ok = await services["books"].update_book_total_pages(book_id, 5)
    assert ok is True
    book = await services["books"].get_book(book_id)
    assert book["total_pages"] == 15


async def test_total_pages_decrements_with_negative_delta(in_memory_pipeline):
    _, services = in_memory_pipeline
    book_id = await services["books"].create_book(
        title="Delta Test",
        class_level="8",
        subject="Science",
        language="en",
        board="NCERT",
        metadata={},
        pdf_asset_id="",
        total_pages=0,
    )

    # First chapter adds 10 pages.
    await services["books"].update_book_total_pages(book_id, 10)
    book = await services["books"].get_book(book_id)
    assert book["total_pages"] == 10

    # Re-ingestion with 7 pages: delta = 7 - 10 = -3.
    await services["books"].update_book_total_pages(book_id, -3)
    book = await services["books"].get_book(book_id)
    assert book["total_pages"] == 7


async def test_total_pages_zero_delta_is_noop(in_memory_pipeline):
    _, services = in_memory_pipeline
    book_id = await services["books"].create_book(
        title="Delta Test",
        class_level="8",
        subject="Science",
        language="en",
        board="NCERT",
        metadata={},
        pdf_asset_id="",
        total_pages=0,
    )

    await services["books"].update_book_total_pages(book_id, 5)
    ok = await services["books"].update_book_total_pages(book_id, 0)
    assert ok is True
    book = await services["books"].get_book(book_id)
    assert book["total_pages"] == 5
