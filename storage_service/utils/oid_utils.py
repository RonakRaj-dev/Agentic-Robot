"""Shared helpers for ObjectId conversion and storage-URL parsing.

These helpers used to be duplicated across ``services/mongo/book_service.py``
(``_to_oid``, ``_parse_storage_url``), ``services/mocks/mock_services.py``
(``_parse_storage_url``), and ``repos/mongo/base_mongo_repo.py`` (``_oid``).
They now live here so there is a single source of truth.
"""
from __future__ import annotations

from typing import Tuple
from urllib.parse import urlparse

from bson import ObjectId


def to_oid(value) -> ObjectId:
    """Coerce a value into an :class:`ObjectId`.

    Accepts ``ObjectId`` instances and ObjectId-valid strings. Raises
    ``ValueError`` for ``None`` or invalid input — passing ``None`` almost
    always indicates a missing ``chapter_id`` upstream and should fail
    loudly rather than silently producing a wrong query.
    """
    if value is None:
        raise ValueError(
            "Cannot convert None to ObjectId — this indicates a missing "
            "chapter_id or book_id upstream."
        )
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)
    raise ValueError(
        f"Cannot convert {type(value).__name__} to ObjectId: invalid ObjectId"
    )


def parse_storage_url(storage_url: str) -> Tuple[str, str]:
    """Split a MinIO URL of the form ``http://host/<bucket>/<key>``.

    Returns ``(bucket, key)``.  Both components default to ``""`` when
    the URL does not contain them.
    """
    parsed = urlparse(storage_url)
    parts = parsed.path.lstrip("/").split("/", 1)
    bucket = parts[0] if len(parts) >= 1 else ""
    key = parts[1] if len(parts) >= 2 else ""
    return bucket, key
