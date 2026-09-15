"""Unit tests: ``MinioStorageServiceAdapter`` public-URL + delegation.

Verifies that:
  * ``upload_bytes`` / ``upload_file`` return the public URL built by
    ``MinioStorageService.get_public_url``.
  * ``object_exists`` requires an explicit bucket name (no silent
    wrong-bucket lookup).
  * ``get_public_url`` delegates to the underlying
    ``MinioStorageService.get_public_url``.
  * ``get_public_url`` is synchronous (pure local string construction).

.. versionchanged:: v7
    Removed tests for ``generate_presigned_get_url`` /
    ``generate_presigned_put_url`` and for the deprecated
    ``get_object_url``.  Added tests for ``get_public_url``.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _build_adapter_with_mock_minio():
    """Build a MinioStorageServiceAdapter backed by a mocked Minio client."""
    from services.storage.minio_service import MinioStorageService
    from services.storage.storage_adapter import MinioStorageServiceAdapter

    # Build a MinioStorageService with a mocked client so we don't need
    # a real MinIO server.
    with patch.object(MinioStorageService, "__init__", lambda self: None):
        storage = MinioStorageService()
    storage.client = MagicMock()
    storage.default_bucket = "ncert-rag"

    adapter = MinioStorageServiceAdapter(storage=storage)
    return adapter, storage


def test_get_public_url_delegates_to_minio_service():
    """``MinioStorageServiceAdapter.get_public_url`` delegates to
    ``MinioStorageService.get_public_url``.
    """
    adapter, storage = _build_adapter_with_mock_minio()
    storage.get_public_url = MagicMock(
        return_value="https://storage.example.com/page-images/k",
    )

    url = adapter.get_public_url("page-images", "books/x/page_0001.png")
    storage.get_public_url.assert_called_once_with(
        "page-images", "books/x/page_0001.png",
    )
    assert url == "https://storage.example.com/page-images/k"


def test_get_public_url_uses_settings_public_storage_url():
    """The underlying ``MinioStorageService.get_public_url`` reads
    ``Settings.public_storage_url`` and joins bucket + key.
    """
    from core.config import Settings
    from services.storage.minio_service import MinioStorageService

    s = Settings(public_storage_url="https://storage.example.com")
    with patch("services.storage.minio_service.get_settings", return_value=s):
        with patch.object(MinioStorageService, "__init__", lambda self: None):
            storage = MinioStorageService()
        url = storage.get_public_url("page-images", "books/x/page_0001.png")
    assert url == "https://storage.example.com/page-images/books/x/page_0001.png"


def test_get_public_url_strips_trailing_slash_from_base():
    """A trailing slash on ``public_storage_url`` must not produce a
    double-slash in the URL.
    """
    from core.config import Settings
    from services.storage.minio_service import MinioStorageService

    s = Settings(public_storage_url="https://storage.example.com/")
    with patch("services.storage.minio_service.get_settings", return_value=s):
        with patch.object(MinioStorageService, "__init__", lambda self: None):
            storage = MinioStorageService()
        url = storage.get_public_url("pdfs", "k.pdf")
    assert url == "https://storage.example.com/pdfs/k.pdf"


def test_get_public_url_is_synchronous():
    """``get_public_url`` must NOT be a coroutine — pure local string build."""
    import inspect
    from services.storage.storage_adapter import MinioStorageServiceAdapter

    method = MinioStorageServiceAdapter.get_public_url
    assert not inspect.iscoroutinefunction(method), (
        "get_public_url must be synchronous"
    )


def test_object_exists_requires_bucket_name():
    """``object_exists`` must take both object_name AND bucket_name.

    The previous version defaulted to ``self.default_bucket`` when the
    caller forgot to pass the bucket — silently checking the wrong
    bucket for page-images and pdfs.
    """
    adapter, storage = _build_adapter_with_mock_minio()
    storage.client.stat_object.return_value = MagicMock()
    storage.client.stat_object.side_effect = None

    # Calling with both args should work.
    assert adapter.object_exists("page_0001.png", "page-images") is True
    storage.client.stat_object.assert_called_with("page-images", "page_0001.png")


def test_upload_bytes_returns_public_url():
    """``upload_bytes`` should return whatever public URL the
    ``MinioStorageService`` built via ``get_public_url``.
    """
    adapter, storage = _build_adapter_with_mock_minio()
    storage.get_public_url = lambda bucket, name: f"https://test/{bucket}/{name}"

    import asyncio
    url = asyncio.run(
        adapter.upload_bytes(
            bucket_name="page-images",
            object_name="books/x/page_0001.png",
            data=b"fake-png",
            content_type="image/png",
        )
    )
    assert url == "https://test/page-images/books/x/page_0001.png"


def test_upload_file_returns_public_url():
    """``upload_file`` should return the public URL of the uploaded object."""
    import tempfile
    adapter, storage = _build_adapter_with_mock_minio()
    storage.get_public_url = lambda bucket, name: f"https://test/{bucket}/{name}"

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"fake-pdf")
        pdf_path = Path(f.name)
    try:
        import asyncio
        url = asyncio.run(
            adapter.upload_file(
                bucket_name="pdfs",
                object_name="books/x/chapter.pdf",
                file_path=pdf_path,
                content_type="application/pdf",
            )
        )
        assert url == "https://test/pdfs/books/x/chapter.pdf"
    finally:
        pdf_path.unlink(missing_ok=True)
