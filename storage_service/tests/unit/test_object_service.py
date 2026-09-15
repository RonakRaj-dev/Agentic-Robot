"""Unit tests: ObjectService (in-memory implementation).

The ObjectService is a facade over BookService — these tests verify
that object-lifecycle operations correctly delegate to the underlying
BookService and produce the expected embedded-array mutations.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def _make_book_with_chapter(in_memory_services) -> tuple[str, str]:
    """Helper: create a book + chapter, return (book_id, chapter_id)."""
    book_id = await in_memory_services.book_service.create_book(
        title="T", class_level="8", subject="Science", language="en",
        board="NCERT", metadata={}, pdf_asset_id="", total_pages=0,
    )
    chapter_id = await in_memory_services.book_service.add_chapter(
        book_id=book_id, chapter_no=1, title="Chapter 1",
    )
    return book_id, chapter_id


async def test_append_page_image_creates_object(in_memory_services):
    svc = in_memory_services.object_service
    book_id, chapter_id = await _make_book_with_chapter(in_memory_services)

    obj_id = await svc.append_page_image(
        book_id=book_id,
        chapter_id=chapter_id,
        page_no=1,
        object_key="books/b1/chapters/1/page_0001.png",
        bucket_name="page-images",
        size_bytes=12345,
        plain_text="Hello world",
        word_count=2,
        token_count=3,
        extraction_method="pymupdf",
    )
    assert isinstance(obj_id, str)

    objs = await svc.list_chapter_objects(book_id, chapter_id)
    assert len(objs) == 1
    assert objs[0]["object_type"] == "PAGE_IMAGE"
    assert objs[0]["page_no"] == 1
    assert objs[0]["metadata"]["plain_text"] == "Hello world"
    assert objs[0]["metadata"]["extraction_method"] == "pymupdf"


async def test_list_chapter_objects_empty(in_memory_services):
    svc = in_memory_services.object_service
    book_id, chapter_id = await _make_book_with_chapter(in_memory_services)
    objs = await svc.list_chapter_objects(book_id, chapter_id)
    assert objs == []


async def test_list_chapter_objects_unknown_chapter(in_memory_services):
    svc = in_memory_services.object_service
    book_id, _ = await _make_book_with_chapter(in_memory_services)
    objs = await svc.list_chapter_objects(book_id, "unknown-chapter-id")
    assert objs == []


async def test_get_object_by_id(in_memory_services):
    svc = in_memory_services.object_service
    book_id, chapter_id = await _make_book_with_chapter(in_memory_services)

    obj_id = await svc.append_page_image(
        book_id=book_id, chapter_id=chapter_id, page_no=1,
        object_key="k", bucket_name="b", object_url="u", size_bytes=1,
    )
    obj = await svc.get_object(book_id, chapter_id, obj_id)
    assert obj is not None
    assert obj["id"] == obj_id


async def test_get_object_unknown_returns_none(in_memory_services):
    svc = in_memory_services.object_service
    book_id, chapter_id = await _make_book_with_chapter(in_memory_services)
    obj = await svc.get_object(book_id, chapter_id, "does-not-exist")
    assert obj is None


async def test_clear_chapter_objects(in_memory_services):
    svc = in_memory_services.object_service
    book_id, chapter_id = await _make_book_with_chapter(in_memory_services)
    await svc.append_page_image(
        book_id=book_id, chapter_id=chapter_id, page_no=1,
        object_key="k", bucket_name="b", object_url="u", size_bytes=1,
    )
    await svc.append_page_image(
        book_id=book_id, chapter_id=chapter_id, page_no=2,
        object_key="k2", bucket_name="b", object_url="u", size_bytes=1,
    )
    assert len(await svc.list_chapter_objects(book_id, chapter_id)) == 2

    ok = await svc.clear_chapter_objects(book_id, chapter_id)
    assert ok is True
    assert await svc.list_chapter_objects(book_id, chapter_id) == []
