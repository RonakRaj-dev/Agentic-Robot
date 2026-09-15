"""Unit tests: v6 storage compatibility helpers.

Verifies that :mod:`utils.storage_compat` correctly resolves
``(bucket, object_key)`` from both new (structured) and old
(URL-based) storage references.
"""
from __future__ import annotations

import pytest

from utils.storage_compat import (
    resolve_chapter_pdf_ref,
    resolve_exam_output_ref,
    resolve_object_ref,
    resolve_source_pdf_ref,
)


# ── resolve_object_ref ────────────────────────────────────────────────


def test_resolve_object_ref_from_structured_fields():
    """v6 canonical path: bucket_name + object_key fields."""
    obj = {
        "bucket_name": "page-images",
        "object_key": "books/b/ch1/p1.png",
        "object_url": None,  # v6: None for new uploads
    }
    bucket, key = resolve_object_ref(obj)
    assert bucket == "page-images"
    assert key == "books/b/ch1/p1.png"


def test_resolve_object_ref_from_legacy_url():
    """v5 backward-compat path: parse bucket + key from object_url."""
    obj = {
        # No structured fields — only the legacy URL.
        "object_url": "http://minio:9000/page-images/books/b/ch1/p1.png",
    }
    bucket, key = resolve_object_ref(obj)
    assert bucket == "page-images"
    assert key == "books/b/ch1/p1.png"


def test_resolve_object_ref_prefers_structured_over_url():
    """When both are present, structured fields win."""
    obj = {
        "bucket_name": "page-images",
        "object_key": "books/b/ch1/p1.png",
        "object_url": "http://legacy-url/page-images/different/key.png",
    }
    bucket, key = resolve_object_ref(obj)
    assert bucket == "page-images"
    assert key == "books/b/ch1/p1.png"


def test_resolve_object_ref_returns_none_when_empty():
    assert resolve_object_ref(None) == (None, None)
    assert resolve_object_ref({}) == (None, None)
    assert resolve_object_ref({"object_url": None}) == (None, None)


def test_resolve_object_ref_works_with_pydantic_model():
    """The helper tolerates Pydantic models, not just dicts."""
    from db.models.embedded import EmbeddedObject, ObjectType
    obj = EmbeddedObject(
        object_type=ObjectType.PAGE_IMAGE,
        object_key="books/b/ch1/p1.png",
        bucket_name="page-images",
        mime_type="image/png",
        size_bytes=100,
    )
    bucket, key = resolve_object_ref(obj)
    assert bucket == "page-images"
    assert key == "books/b/ch1/p1.png"


# ── resolve_chapter_pdf_ref ───────────────────────────────────────────


def test_resolve_chapter_pdf_ref_from_structured_fields():
    ch = {
        "pdf_bucket_name": "pdfs",
        "pdf_object_key": "books/b/ch1/chapter.pdf",
        "pdf_object_url": None,
    }
    bucket, key = resolve_chapter_pdf_ref(ch)
    assert bucket == "pdfs"
    assert key == "books/b/ch1/chapter.pdf"


def test_resolve_chapter_pdf_ref_from_legacy_url():
    ch = {
        "pdf_object_url": "http://minio:9000/pdfs/books/b/ch1/chapter.pdf",
    }
    bucket, key = resolve_chapter_pdf_ref(ch)
    assert bucket == "pdfs"
    assert key == "books/b/ch1/chapter.pdf"


def test_resolve_chapter_pdf_ref_returns_none_when_empty():
    assert resolve_chapter_pdf_ref(None) == (None, None)
    assert resolve_chapter_pdf_ref({}) == (None, None)


# ── resolve_source_pdf_ref ────────────────────────────────────────────


def test_resolve_source_pdf_ref_from_structured_fields():
    book = {
        "source_pdf": {
            "bucket_name": "pdfs",
            "object_key": "books/source.pdf",
            "object_url": None,
        }
    }
    bucket, key = resolve_source_pdf_ref(book)
    assert bucket == "pdfs"
    assert key == "books/source.pdf"


def test_resolve_source_pdf_ref_from_legacy_url():
    book = {
        "source_pdf": {
            "object_url": "http://minio:9000/pdfs/books/source.pdf",
        }
    }
    bucket, key = resolve_source_pdf_ref(book)
    assert bucket == "pdfs"
    assert key == "books/source.pdf"


def test_resolve_source_pdf_ref_returns_none_when_no_source_pdf():
    assert resolve_source_pdf_ref({}) == (None, None)
    assert resolve_source_pdf_ref({"source_pdf": None}) == (None, None)


# ── resolve_exam_output_ref ───────────────────────────────────────────


def test_resolve_exam_output_ref_questions_only_structured():
    outputs = {
        "questions_only_bucket": "ncert-rag",
        "questions_only_object_key": "exports/e1/q.pdf",
        "questions_with_answers_bucket": "ncert-rag",
        "questions_with_answers_object_key": "exports/e1/qa.pdf",
    }
    b, k = resolve_exam_output_ref(outputs, "questions_only")
    assert b == "ncert-rag"
    assert k == "exports/e1/q.pdf"
    b, k = resolve_exam_output_ref(outputs, "questions_with_answers")
    assert b == "ncert-rag"
    assert k == "exports/e1/qa.pdf"


def test_resolve_exam_output_ref_questions_only_legacy_url():
    outputs = {
        "questions_only": "http://minio:9000/ncert-rag/exports/e1/q.pdf",
        "questions_with_answers": "http://minio:9000/ncert-rag/exports/e1/qa.pdf",
    }
    b, k = resolve_exam_output_ref(outputs, "questions_only")
    assert b == "ncert-rag"
    assert k == "exports/e1/q.pdf"
    b, k = resolve_exam_output_ref(outputs, "questions_with_answers")
    assert b == "ncert-rag"
    assert k == "exports/e1/qa.pdf"


def test_resolve_exam_output_ref_prefers_structured_over_url():
    outputs = {
        "questions_only_bucket": "ncert-rag",
        "questions_only_object_key": "exports/e1/new.pdf",
        "questions_only": "http://minio:9000/ncert-rag/exports/e1/old.pdf",
    }
    b, k = resolve_exam_output_ref(outputs, "questions_only")
    assert k == "exports/e1/new.pdf"


def test_resolve_exam_output_ref_returns_none_when_empty():
    assert resolve_exam_output_ref(None, "questions_only") == (None, None)
    assert resolve_exam_output_ref({}, "questions_only") == (None, None)


# ── End-to-end v7 usage pattern ───────────────────────────────────────


def test_v7_end_to_end_pattern_with_in_memory_storage():
    """The full v7 pattern: read structured ref → generate public URL.

    Demonstrates the intended consumer flow without needing a real
    MinIO server.  No signing, no expiry — buckets are publicly
    downloadable.
    """
    from factory import build_in_memory_registry

    reg = build_in_memory_registry()
    storage = reg.storage_service

    # Simulate a stored object (as if loaded from MongoDB).
    stored_obj = {
        "id": "obj_1",
        "object_type": "PAGE_IMAGE",
        "bucket_name": "page-images",
        "object_key": "books/b/ch1/p1.png",
        "object_url": None,  # v7: None for new uploads
        "page_no": 1,
        "mime_type": "image/png",
        "size_bytes": 12345,
        "metadata": {"plain_text": "hello"},
    }

    # 1. Resolve (bucket, object_key) — works for both old and new records.
    bucket, key = resolve_object_ref(stored_obj)
    assert bucket == "page-images"
    assert key == "books/b/ch1/p1.png"

    # 2. Generate a public URL on demand.
    url = storage.get_public_url(bucket, key)
    assert url == "memory://page-images/books/b/ch1/p1.png"
