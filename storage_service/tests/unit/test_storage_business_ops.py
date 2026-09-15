"""Unit tests: StorageService business operations (in-memory implementation).

Verifies that the business-operation methods (upload_pdf,
upload_page_image, upload_export) return a :class:`StorageRef` with the
correct bucket name and object key — and that bucket-name encapsulation
works (the caller never reads settings).

.. versionchanged:: v7
    ``StorageRef`` no longer carries a ``url`` field.  Tests that need
    an access URL call ``get_public_url``.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.asyncio


async def test_upload_pdf_returns_storage_ref_with_pdfs_bucket(in_memory_services):
    svc = in_memory_services.storage_service
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"fake-pdf-bytes")
        pdf_path = Path(f.name)

    try:
        ref = await svc.upload_pdf(
            book_id="book_001", chapter_no=3, file_path=pdf_path,
        )
        # StorageRef carries bucket name + object key.
        assert ref.bucket_name == "pdfs"
        assert ref.object_key == "books/book_001/chapters/3/chapter.pdf"
        # Object should exist in the in-memory store.
        assert svc.has_object("pdfs", "books/book_001/chapters/3/chapter.pdf")
    finally:
        pdf_path.unlink(missing_ok=True)


async def test_upload_page_image_returns_storage_ref_with_page_images_bucket(in_memory_services):
    svc = in_memory_services.storage_service
    ref = await svc.upload_page_image(
        book_id="book_001", chapter_no=3, page_no=7, png_bytes=b"fake-png",
    )
    assert ref.bucket_name == "page-images"
    assert ref.object_key == "books/book_001/chapters/3/page_0007.png"
    assert svc.has_object("page-images", "books/book_001/chapters/3/page_0007.png")


async def test_upload_page_image_zero_pads_page_no(in_memory_services):
    svc = in_memory_services.storage_service
    ref = await svc.upload_page_image(
        book_id="b", chapter_no=1, page_no=1, png_bytes=b"x",
    )
    assert "page_0001.png" in ref.object_key


async def test_upload_export_returns_storage_ref(in_memory_services):
    svc = in_memory_services.storage_service
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"fake-pdf")
        pdf_path = Path(f.name)

    try:
        ref = await svc.upload_export(
            exam_id="exam_001", filename="questions_only.pdf", file_path=pdf_path,
        )
        assert ref.object_key == "exports/exam_001/questions_only.pdf"
        assert ref.bucket_name  # non-empty
    finally:
        pdf_path.unlink(missing_ok=True)


async def test_delete_object(in_memory_services):
    svc = in_memory_services.storage_service
    await svc.upload_page_image(
        book_id="b", chapter_no=1, page_no=1, png_bytes=b"x",
    )
    key = "books/b/chapters/1/page_0001.png"
    assert svc.has_object("page-images", key)
    ok = await svc.delete_object("page-images", key)
    assert ok is True
    assert not svc.has_object("page-images", key)


async def test_object_exists(in_memory_services):
    svc = in_memory_services.storage_service
    await svc.upload_page_image(
        book_id="b", chapter_no=1, page_no=1, png_bytes=b"x",
    )
    assert svc.object_exists("books/b/chapters/1/page_0001.png", "page-images") is True
    assert svc.object_exists("does-not-exist", "page-images") is False


async def test_ensure_bucket_is_noop_in_memory(in_memory_services):
    svc = in_memory_services.storage_service
    # Should not raise.
    svc.ensure_bucket()


# ── v7: public URL generation ────────────────────────────────────────


async def test_get_public_url_returns_direct_url(in_memory_services):
    """v7: ``get_public_url`` returns a deterministic ``memory://`` URL.

    The URL encodes bucket + key — no signing, no expiry.
    """
    svc = in_memory_services.storage_service
    url = svc.get_public_url(
        "page-images", "books/b/chapters/1/page_0001.png",
    )
    # The mock URL encodes bucket + key so tests can assert.
    assert url == "memory://page-images/books/b/chapters/1/page_0001.png"


async def test_get_public_url_for_pdfs_bucket(in_memory_services):
    svc = in_memory_services.storage_service
    url = svc.get_public_url(
        "pdfs", "books/b/chapters/1/chapter.pdf",
    )
    assert url == "memory://pdfs/books/b/chapters/1/chapter.pdf"


async def test_get_public_url_is_synchronous(in_memory_services):
    """``get_public_url`` must NOT be a coroutine — pure local string build."""
    import inspect
    from services.mocks.mock_services import InMemoryStorageService
    method = InMemoryStorageService.get_public_url
    assert not inspect.iscoroutinefunction(method), (
        "get_public_url must be synchronous"
    )


async def test_upload_file_returns_public_url(in_memory_services):
    """``upload_file`` (low-level) returns the public URL of the uploaded object."""
    import tempfile
    svc = in_memory_services.storage_service
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"fake-pdf")
        pdf_path = Path(f.name)
    try:
        url = await svc.upload_file(
            bucket_name="pdfs", object_name="x/y.pdf",
            file_path=pdf_path, content_type="application/pdf",
        )
        assert url == "memory://pdfs/x/y.pdf"
    finally:
        pdf_path.unlink(missing_ok=True)


async def test_upload_bytes_returns_public_url(in_memory_services):
    """``upload_bytes`` (low-level) returns the public URL of the uploaded object."""
    svc = in_memory_services.storage_service
    url = await svc.upload_bytes(
        bucket_name="page-images", object_name="x/y.png",
        data=b"fake-png", content_type="image/png",
    )
    assert url == "memory://page-images/x/y.png"
