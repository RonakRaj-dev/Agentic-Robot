"""Storage service interface — the SINGLE API in front of object storage.

The architecture document (section 3, "Storage service" component)
requires that no component other than the StorageService touch MinIO.
This interface exposes **business operations** (``upload_pdf``,
``upload_page_image``, ``upload_export``) rather than low-level S3 verbs
(put_object, fput_object).  Callers should not need to know bucket
names or content types — those are derived from the operation type.

The business operations return a :class:`StorageRef` carrying the
bucket name and object key.  As of v7 the buckets are publicly
downloadable, so anyone who needs an access URL calls
:meth:`get_public_url` — there are no presigned URLs and no stored
persistent URLs.

A thin low-level escape hatch (``upload_file`` / ``upload_bytes`` /
``delete_object``) is retained for callers that need to perform raw
uploads against an explicit bucket + object name (e.g. the legacy
book-level source-PDF path).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StorageRef:
    """Reference to an uploaded object.

    Returned by the business-operation methods so callers never need to
    re-derive the bucket name or object key from settings.
    """

    bucket_name: str
    object_key: str


class IStorageService(ABC):
    """Object-storage abstraction (MinIO in production)."""

    # ── Business operations (preferred for new code) ─────────────────

    @abstractmethod
    async def upload_pdf(
        self,
        book_id: str,
        chapter_no: int,
        file_path: Path,
    ) -> StorageRef:
        """Upload a chapter PDF to the ``pdfs`` bucket.

        Returns a :class:`StorageRef` carrying the bucket name and
        object key.  Object key convention:
        ``books/{book_id}/chapters/{chapter_no}/chapter.pdf``.
        """
        ...

    @abstractmethod
    async def upload_page_image(
        self,
        book_id: str,
        chapter_no: int,
        page_no: int,
        png_bytes: bytes,
    ) -> StorageRef:
        """Upload a single page PNG to the ``page-images`` bucket.

        Returns a :class:`StorageRef`.  Object key convention:
        ``books/{book_id}/chapters/{chapter_no}/page_{page_no:04d}.png``.
        """
        ...

    @abstractmethod
    async def upload_export(
        self,
        exam_id: str,
        filename: str,
        file_path: Path,
    ) -> StorageRef:
        """Upload a rendered exam export (questions-only or Q&A PDF).

        Returns a :class:`StorageRef`.  Object key convention:
        ``exports/{exam_id}/{filename}``.
        """
        ...

    # ── Public URL generation (v7 — preferred for access URLs) ──────

    @abstractmethod
    def get_public_url(self, bucket_name: str, object_name: str) -> str:
        """Build a direct public URL for an object.

        Buckets are configured as publicly downloadable, so no signing
        is required.  The URL is constructed by joining
        ``Settings.public_storage_url`` + ``bucket_name`` +
        ``object_name``.

        This is the SINGLE way to obtain an access URL for a stored
        object.  URLs are generated on demand and never persisted to
        MongoDB — only ``bucket_name`` + ``object_key`` are stored.

        This method is synchronous because it performs only local
        string construction — no network I/O.
        """
        ...

    # ── Low-level operations ────────────────────────────────────────

    @abstractmethod
    async def upload_file(
        self,
        bucket_name: str,
        object_name: str,
        file_path: Path,
        content_type: str | None = None,
    ) -> str:
        """Upload a file.  Returns the public object URL."""
        ...

    @abstractmethod
    async def upload_bytes(
        self,
        bucket_name: str,
        object_name: str,
        data: bytes,
        content_type: str | None = None,
    ) -> str:
        """Upload raw bytes.  Returns the public object URL."""
        ...

    @abstractmethod
    async def delete_object(self, bucket_name: str, object_name: str) -> bool:
        ...

    # ── Setup-time helpers (NOT per-call) ────────────────────────────

    @abstractmethod
    def ensure_bucket(self) -> None:
        """Create all known buckets if they don't exist.  Called once at startup."""
        ...

    @abstractmethod
    def object_exists(self, object_name: str, bucket_name: str) -> bool:
        """Return True if the object exists in the bucket."""
        ...
