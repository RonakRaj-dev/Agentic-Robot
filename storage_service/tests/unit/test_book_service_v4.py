"""Unit tests: BookService business methods (v5 service layer).

Covers:
  * get_book_by_code
  * get_chapter
  * add_chapter (idempotent)
  * add_chapters (batched, idempotent)
  * append_page_object (single)
  * append_page_objects (batched $push + $each)
  * append_processed_pages (batched, builds EmbeddedObject internally)
  * append_processed_page (single-page convenience wrapper)
  * finalize_chapter_ingestion (processed_pages + page_end in one write)

The full re-ingestion idempotency tests live in
``test_reingestion_idempotency.py``.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def _make_book(svc) -> str:
    return await svc.create_book(
        title="T", class_level="8", subject="Science", language="en",
        board="NCERT", metadata={}, pdf_asset_id="", total_pages=0,
    )


# ── get_book_by_code ─────────────────────────────────────────────────


async def test_get_book_by_code_returns_id(in_memory_services):
    svc = in_memory_services.book_service
    book_id = await svc.create_book(
        title="Maths", class_level="10", subject="Mathematics",
        language="en", board="CBSE", metadata={}, pdf_asset_id="",
        total_pages=0,
    )
    found = await svc.get_book_by_code(
        class_no=10, subject="Mathematics", title="Maths", board="CBSE",
    )
    assert found == book_id


async def test_get_book_by_code_without_board(in_memory_services):
    svc = in_memory_services.book_service
    book_id = await svc.create_book(
        title="Maths", class_level="10", subject="Mathematics",
        language="en", board="CBSE", metadata={}, pdf_asset_id="",
        total_pages=0,
    )
    found = await svc.get_book_by_code(
        class_no=10, subject="Mathematics", title="Maths", board=None,
    )
    assert found == book_id


async def test_get_book_by_code_returns_none_when_missing(in_memory_services):
    svc = in_memory_services.book_service
    found = await svc.get_book_by_code(
        class_no=99, subject="Nope", title="Nope", board="Nope",
    )
    assert found is None


# ── add_chapter ──────────────────────────────────────────────────────


async def test_add_chapter_is_idempotent(in_memory_services):
    svc = in_memory_services.book_service
    book_id = await _make_book(svc)
    ch1 = await svc.add_chapter(book_id=book_id, chapter_no=1, title="Ch 1")
    ch1_again = await svc.add_chapter(book_id=book_id, chapter_no=1, title="Ch 1")
    assert ch1 == ch1_again


# ── add_chapters (batched) ───────────────────────────────────────────


async def test_add_chapters_batch_creates_all(in_memory_services):
    svc = in_memory_services.book_service
    book_id = await _make_book(svc)
    ok = await svc.add_chapters(book_id=book_id, chapters=[
        {"chapter_no": 1, "title": "Ch 1", "pdf_filename": "c1.pdf"},
        {"chapter_no": 2, "title": "Ch 2", "pdf_filename": "c2.pdf"},
        {"chapter_no": 3, "title": "Ch 3", "pdf_filename": "c3.pdf"},
    ])
    assert ok is True
    book = await svc.get_book(book_id)
    assert len(book["chapters"]) == 3
    assert [c["chapter_no"] for c in book["chapters"]] == [1, 2, 3]


async def test_add_chapters_is_idempotent_on_chapter_no(in_memory_services):
    """Batch append skips chapters whose chapter_no already exists."""
    svc = in_memory_services.book_service
    book_id = await _make_book(svc)
    await svc.add_chapter(book_id=book_id, chapter_no=1, title="Existing")
    await svc.add_chapters(book_id=book_id, chapters=[
        {"chapter_no": 1, "title": "Duplicate"},
        {"chapter_no": 2, "title": "New"},
    ])
    book = await svc.get_book(book_id)
    assert len(book["chapters"]) == 2
    # chapter_no=1 keeps its original title.
    ch1 = next(c for c in book["chapters"] if c["chapter_no"] == 1)
    assert ch1["title"] == "Existing"


async def test_add_chapters_empty_list_is_noop(in_memory_services):
    svc = in_memory_services.book_service
    book_id = await _make_book(svc)
    ok = await svc.add_chapters(book_id=book_id, chapters=[])
    assert ok is True
    book = await svc.get_book(book_id)
    assert book["chapters"] == []


# ── get_chapter ──────────────────────────────────────────────────────


async def test_get_chapter_returns_chapter_dict(in_memory_services):
    svc = in_memory_services.book_service
    book_id = await _make_book(svc)
    chapter_id = await svc.add_chapter(
        book_id=book_id, chapter_no=1, title="Chapter 1",
        page_start=1, page_end=10, pdf_filename="chap1.pdf",
    )
    chapter = await svc.get_chapter(book_id=book_id, chapter_no=1)
    assert chapter is not None
    assert chapter["id"] == chapter_id
    assert chapter["chapter_no"] == 1
    assert chapter["title"] == "Chapter 1"
    assert chapter["page_start"] == 1
    assert chapter["page_end"] == 10
    assert chapter["pdf_filename"] == "chap1.pdf"


async def test_get_chapter_returns_none_when_missing(in_memory_services):
    svc = in_memory_services.book_service
    book_id = await _make_book(svc)
    chapter = await svc.get_chapter(book_id=book_id, chapter_no=99)
    assert chapter is None


# ── append_page_object / append_page_objects ─────────────────────────


async def _make_chapter(svc, book_id: str, chapter_no: int = 1) -> str:
    return await svc.add_chapter(book_id=book_id, chapter_no=chapter_no, title="Ch")


async def test_append_page_object_single(in_memory_services):
    from db.models.embedded import EmbeddedObject, ObjectType
    svc = in_memory_services.book_service
    book_id = await _make_book(svc)
    chapter_id = await _make_chapter(svc, book_id)
    po = EmbeddedObject(
        object_type=ObjectType.PAGE_IMAGE,
        object_key="k", bucket_name="b", object_url="u",
        page_no=1, mime_type="image/png", size_bytes=1,
    )
    ok = await svc.append_page_object(
        book_id=book_id, chapter_id=chapter_id, page_object=po,
    )
    assert ok is True
    ch = await svc.get_chapter(book_id, 1)
    assert len(ch["objects"]) == 1


async def test_append_page_objects_batch(in_memory_services):
    """Batch append persists all objects in one logical write."""
    from db.models.embedded import EmbeddedObject, ObjectType
    svc = in_memory_services.book_service
    book_id = await _make_book(svc)
    chapter_id = await _make_chapter(svc, book_id)
    pos = [
        EmbeddedObject(
            object_type=ObjectType.PAGE_IMAGE,
            object_key=f"k{i}", bucket_name="b", object_url=f"u{i}",
            page_no=i, mime_type="image/png", size_bytes=i,
        )
        for i in range(1, 6)
    ]
    ok = await svc.append_page_objects(
        book_id=book_id, chapter_id=chapter_id, page_objects=pos,
    )
    assert ok is True
    ch = await svc.get_chapter(book_id, 1)
    assert len(ch["objects"]) == 5
    assert [o["page_no"] for o in ch["objects"]] == [1, 2, 3, 4, 5]


async def test_append_page_objects_empty_list_is_noop(in_memory_services):
    svc = in_memory_services.book_service
    book_id = await _make_book(svc)
    chapter_id = await _make_chapter(svc, book_id)
    ok = await svc.append_page_objects(
        book_id=book_id, chapter_id=chapter_id, page_objects=[],
    )
    assert ok is True
    ch = await svc.get_chapter(book_id, 1)
    assert ch["objects"] == []


# ── append_processed_pages (batched) ─────────────────────────────────


async def test_append_processed_pages_batch_creates_page_images(in_memory_services):
    svc = in_memory_services.book_service
    book_id = await _make_book(svc)
    chapter_id = await _make_chapter(svc, book_id)
    # v6: object_url key is optional — omitted here.
    ids = await svc.append_processed_pages(
        book_id=book_id, chapter_id=chapter_id,
        pages=[
            {"page_no": 1, "plain_text": "p1", "word_count": 2, "token_count": 3,
             "extraction_method": "pymupdf", "object_key": "k1",
             "bucket_name": "page-images", "size_bytes": 10},
            {"page_no": 2, "plain_text": "p2", "word_count": 4, "token_count": 5,
             "extraction_method": "pymupdf", "object_key": "k2",
             "bucket_name": "page-images", "size_bytes": 20},
            {"page_no": 3, "plain_text": "p3", "word_count": 6, "token_count": 7,
             "extraction_method": "pymupdf", "object_key": "k3",
             "bucket_name": "page-images", "size_bytes": 30},
        ],
    )
    assert len(ids) == 3
    ch = await svc.get_chapter(book_id, 1)
    assert len(ch["objects"]) == 3
    for i, obj in enumerate(ch["objects"], start=1):
        assert obj["object_type"] == "PAGE_IMAGE"
        assert obj["page_no"] == i
        assert obj["metadata"]["plain_text"] == f"p{i}"
        assert obj["metadata"]["extraction_method"] == "pymupdf"


async def test_append_processed_page_single_convenience(in_memory_services):
    svc = in_memory_services.book_service
    book_id = await _make_book(svc)
    chapter_id = await _make_chapter(svc, book_id)
    # v6: object_url is optional and defaults to None.
    obj_id = await svc.append_processed_page(
        book_id=book_id, chapter_id=chapter_id, page_no=1,
        plain_text="Hello world", word_count=2, token_count=3,
        extraction_method="pymupdf",
        object_key="books/b1/ch1/p1.png", bucket_name="page-images",
        size_bytes=12345,
    )
    assert isinstance(obj_id, str)
    ch = await svc.get_chapter(book_id, 1)
    assert len(ch["objects"]) == 1
    obj = ch["objects"][0]
    assert obj["object_type"] == "PAGE_IMAGE"
    assert obj["page_no"] == 1
    assert obj["metadata"]["plain_text"] == "Hello world"


# ── finalize_chapter_ingestion ───────────────────────────────────────


async def test_finalize_chapter_ingestion_stamps_processed_pages_and_page_end(in_memory_services):
    svc = in_memory_services.book_service
    book_id = await _make_book(svc)
    chapter_id = await _make_chapter(svc, book_id)
    ok = await svc.finalize_chapter_ingestion(
        book_id=book_id, chapter_id=chapter_id,
        processed_pages=22, page_end=22,
    )
    assert ok is True
    ch = await svc.get_chapter(book_id, 1)
    assert ch["processed_pages"] == 22
    assert ch["page_end"] == 22


async def test_finalize_chapter_ingestion_without_page_end(in_memory_services):
    svc = in_memory_services.book_service
    book_id = await _make_book(svc)
    chapter_id = await _make_chapter(svc, book_id)
    await svc.finalize_chapter_ingestion(
        book_id=book_id, chapter_id=chapter_id,
        processed_pages=5, page_end=None,
    )
    ch = await svc.get_chapter(book_id, 1)
    assert ch["processed_pages"] == 5


# ── preferred_llm / no raw_title ──────────────────────────────────


async def test_add_chapter_threads_preferred_llm(in_memory_services):
    """preferred_llm passed to add_chapter appears on the stored chapter."""
    svc = in_memory_services.book_service
    book_id = await _make_book(svc)
    await svc.add_chapter(
        book_id=book_id, chapter_no=1, title="Ch 1",
        preferred_llm="gpt-4o",
    )
    ch = await svc.get_chapter(book_id, 1)
    assert ch["preferred_llm"] == "gpt-4o"
    assert "raw_title" not in ch


async def test_add_chapters_threads_preferred_llm(in_memory_services):
    """preferred_llm passed in batch dicts appears on stored chapters."""
    svc = in_memory_services.book_service
    book_id = await _make_book(svc)
    await svc.add_chapters(book_id=book_id, chapters=[
        {"chapter_no": 1, "title": "Ch 1", "preferred_llm": "claude-3"},
        {"chapter_no": 2, "title": "Ch 2"},  # no preferred_llm
    ])
    book = await svc.get_book(book_id)
    assert book["chapters"][0]["preferred_llm"] == "claude-3"
    assert book["chapters"][1]["preferred_llm"] is None
    for ch in book["chapters"]:
        assert "raw_title" not in ch


async def test_chapter_default_preferred_llm_is_none(in_memory_services):
    """When preferred_llm is not provided, the field is None (not missing)."""
    svc = in_memory_services.book_service
    book_id = await _make_book(svc)
    await svc.add_chapter(book_id=book_id, chapter_no=1, title="Ch 1")
    ch = await svc.get_chapter(book_id, 1)
    assert ch.get("preferred_llm") is None
    assert "raw_title" not in ch
