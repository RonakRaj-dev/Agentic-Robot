"""Backward-compatibility helpers for storage references.

In v6+, persistent URLs are no longer written to MongoDB — only
``bucket_name`` + ``object_key`` are stored.  Old records, however,
may carry a ``*_url`` field (and may even be missing the structured
``*_bucket`` / ``*_object_key`` fields if they were written before
those fields existed).

These helpers normalise both shapes into a single ``(bucket, object_key)``
tuple so consumers can call
``storage.get_public_url(bucket, object_key)`` without
caring whether the underlying record is old or new.

Typical usage::

    from utils.storage_compat import resolve_object_ref

    bucket, key = resolve_object_ref(stored_page_object)
    if bucket and key:
        url = storage.get_public_url(bucket, key)

The helpers tolerate dict, Pydantic model, and ``None`` inputs.
"""
from __future__ import annotations

from typing import Any, Optional, Tuple

from utils.oid_utils import parse_storage_url


def _get(obj: Any, name: str, default: Any = None) -> Any:
    """Read ``name`` from a dict OR a Pydantic model OR an arbitrary object."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    # Pydantic v2 model — use attribute access (it raises AttributeError
    # for unknown fields, which we convert to default).
    try:
        return getattr(obj, name, default)
    except AttributeError:
        return default


def resolve_object_ref(obj: Any) -> Tuple[Optional[str], Optional[str]]:
    """Return ``(bucket_name, object_key)`` for an :class:`EmbeddedObject`.

    Resolution order:
      1. ``bucket_name`` + ``object_key`` fields (canonical v6 path).
      2. ``object_url`` field parsed via :func:`parse_storage_url`
         (legacy v5 path).

    Returns ``(None, None)`` if neither path yields a usable reference.
    """
    if obj is None:
        return None, None

    bucket = _get(obj, "bucket_name")
    key = _get(obj, "object_key")
    if bucket and key:
        return str(bucket), str(key)

    url = _get(obj, "object_url")
    if url:
        b, k = parse_storage_url(url)
        if b and k:
            return b, k

    return None, None


def resolve_chapter_pdf_ref(chapter: Any) -> Tuple[Optional[str], Optional[str]]:
    """Return ``(bucket_name, object_key)`` for a chapter's PDF reference.

    Resolution order:
      1. ``pdf_bucket_name`` + ``pdf_object_key`` fields (canonical v6).
      2. ``pdf_object_url`` field parsed via :func:`parse_storage_url`
         (legacy v5).

    Returns ``(None, None)`` if the chapter has no PDF reference.
    """
    if chapter is None:
        return None, None

    bucket = _get(chapter, "pdf_bucket_name")
    key = _get(chapter, "pdf_object_key")
    if bucket and key:
        return str(bucket), str(key)

    url = _get(chapter, "pdf_object_url")
    if url:
        b, k = parse_storage_url(url)
        if b and k:
            return b, k

    return None, None


def resolve_source_pdf_ref(book: Any) -> Tuple[Optional[str], Optional[str]]:
    """Return ``(bucket_name, object_key)`` for a Book's source PDF.

    The source PDF is stored as an :class:`EmbeddedObject` on
    ``book.source_pdf``.  This helper delegates to
    :func:`resolve_object_ref`.

    Returns ``(None, None)`` if the book has no source PDF.
    """
    return resolve_object_ref(_get(book, "source_pdf"))


def resolve_exam_output_ref(
    outputs: Any, which: str,
) -> Tuple[Optional[str], Optional[str]]:
    """Return ``(bucket_name, object_key)`` for an ExamOutputs entry.

    Args:
        outputs: An :class:`ExamOutputs` instance or compatible dict.
        which: Either ``"questions_only"`` or ``"questions_with_answers"``.

    Resolution order:
      1. ``{which}_bucket`` + ``{which}_object_key`` (canonical v6).
      2. ``{which}`` (legacy URL string) parsed via
         :func:`parse_storage_url`.

    Returns ``(None, None)`` if the output has no reference.
    """
    if outputs is None:
        return None, None

    bucket = _get(outputs, f"{which}_bucket")
    key = _get(outputs, f"{which}_object_key")
    if bucket and key:
        return str(bucket), str(key)

    url = _get(outputs, which)
    if url:
        b, k = parse_storage_url(url)
        if b and k:
            return b, k

    return None, None
