"""Regression test: ensure PyObjectId fields remain ObjectId in to_mongo().

Schema v3 — tests EmbeddedChapter and EmbeddedObject only.
"""
from __future__ import annotations

import pytest
from bson import ObjectId
from db.models.embedded import (
    EmbeddedChapter,
    EmbeddedObject,
    ExtractionMethod,
    ObjectType,
)


class TestEmbeddedObjectIdSerialization:
    """Ensure ObjectId fields stay as ObjectId in to_mongo() output."""

    def test_chapter_id_is_objectid(self):
        ch = EmbeddedChapter(chapter_no=1, title="Test Chapter")
        data = ch.to_mongo()
        assert isinstance(
            data["id"], ObjectId
        ), f"chapter.id must be ObjectId in to_mongo(), got {type(data['id']).__name__}"

    def test_chapter_id_matches_in_memory(self):
        ch = EmbeddedChapter(chapter_no=1, title="Test Chapter")
        assert isinstance(ch.id, ObjectId)

    def test_object_id_is_objectid(self):
        obj = EmbeddedObject(
            object_type=ObjectType.PAGE_IMAGE,
            object_key="page_0001.png",
            bucket_name="page-images",
            mime_type="image/png",
            size_bytes=100,
        )
        data = obj.to_mongo()
        assert isinstance(
            data["id"], ObjectId
        ), f"object.id must be ObjectId in to_mongo(), got {type(data['id']).__name__}"

    def test_no_string_ids_in_mongo_output(self):
        ch = EmbeddedChapter(chapter_no=1, title="Test")
        data = ch.to_mongo()
        assert data["id"] != "string"

    @pytest.mark.parametrize(
        "model_cls,kwargs",
        [
            (EmbeddedChapter, {"chapter_no": 1, "title": "T"}),
            (EmbeddedObject, {"object_type": ObjectType.PAGE_IMAGE, "object_key": "k", "bucket_name": "b", "mime_type": "image/png", "size_bytes": 1}),
        ],
    )
    def test_serialization_roundtrip(self, model_cls, kwargs):
        obj = model_cls(**kwargs)
        data = obj.to_mongo()
        assert isinstance(data["id"], ObjectId)

    def test_to_mongo_returns_valid_dict(self):
        ch = EmbeddedChapter(chapter_no=1, title="T")
        data = ch.to_mongo()
        assert isinstance(data, dict)
        assert isinstance(data["id"], ObjectId)

    @pytest.mark.parametrize(
        "model_cls,kwargs",
        [
            (EmbeddedChapter, {"chapter_no": 1, "title": "T"}),
            (EmbeddedObject, {"object_type": ObjectType.PAGE_IMAGE, "object_key": "k", "bucket_name": "b", "mime_type": "image/png", "size_bytes": 1}),
        ],
    )
    def test_all_embedded_models_id_is_objectid(self, model_cls, kwargs):
        obj = model_cls(**kwargs)
        data = obj.to_mongo()
        assert isinstance(data["id"], ObjectId)

    def test_empty_chapter_has_empty_objects(self):
        ch = EmbeddedChapter(chapter_no=1, title="T")
        data = ch.to_mongo()
        assert "objects" in data
        assert data["objects"] == []

    def test_chapter_has_processed_pages_field(self):
        """Verify EmbeddedChapter has a processed_pages counter."""
        ch = EmbeddedChapter(chapter_no=1, title="T")
        assert ch.processed_pages == 0

    def test_chapter_has_pdf_ref_fields(self):
        """Verify EmbeddedChapter has chapter PDF reference fields.

        v6: ``pdf_object_url`` is still accepted (Optional, defaults
        to None) for backward compatibility with old records.
        """
        ch = EmbeddedChapter(
            chapter_no=1,
            title="T",
            pdf_object_key="books/.../chapter.pdf",
            pdf_bucket_name="pdfs",
            pdf_object_url=None,  # v6: None for new uploads
            pdf_size_bytes=520000,
        )
        data = ch.to_mongo()
        assert data["pdf_object_key"] == "books/.../chapter.pdf"
        assert data["pdf_bucket_name"] == "pdfs"
        assert data["pdf_size_bytes"] == 520000
        # v6: pdf_object_url is excluded from to_mongo() output when
        # None (because of exclude_none=True in _EmbeddedBase.to_mongo).
        assert "pdf_object_url" not in data

    def test_chapter_legacy_pdf_url_still_supported(self):
        """v6 backward-compat: old records carrying a URL still deserialise."""
        ch = EmbeddedChapter(
            chapter_no=1,
            title="T",
            pdf_object_key="books/.../chapter.pdf",
            pdf_bucket_name="pdfs",
            pdf_object_url="http://minio:9000/pdfs/books/.../chapter.pdf",
            pdf_size_bytes=520000,
        )
        data = ch.to_mongo()
        # Legacy URL is preserved when explicitly set.
        assert data["pdf_object_url"] == "http://minio:9000/pdfs/books/.../chapter.pdf"

    def test_chapter_and_object_both_have_objectid(self):
        ch = EmbeddedChapter(chapter_no=1, title="T")
        obj = EmbeddedObject(
            object_type=ObjectType.PAGE_IMAGE,
            object_key="page_0001.png",
            bucket_name="page-images",
            mime_type="image/png",
            size_bytes=1,
        )
        ch_data = ch.to_mongo()
        obj_data = obj.to_mongo()
        assert isinstance(ch_data["id"], ObjectId)
        assert isinstance(obj_data["id"], ObjectId)

    def test_object_carries_text_metadata(self):
        """Verify EmbeddedObject can carry extracted text in metadata."""
        obj = EmbeddedObject(
            object_type=ObjectType.PAGE_IMAGE,
            object_key="page_0001.png",
            bucket_name="page-images",
            page_no=1,
            mime_type="image/png",
            size_bytes=123456,
            metadata={
                "plain_text": "Hello world",
                "word_count": 2,
                "token_count": 3,
                "extraction_method": ExtractionMethod.PYMUPDF.value,
            },
        )
        data = obj.to_mongo()
        assert data["metadata"]["plain_text"] == "Hello world"
        assert data["metadata"]["extraction_method"] == "pymupdf"


class TestChapterPreferredLlmField:
    """Verify preferred_llm field behaviour on EmbeddedChapter."""

    def test_chapter_has_preferred_llm_default_none(self):
        """preferred_llm defaults to None and is excluded from to_mongo()."""
        ch = EmbeddedChapter(chapter_no=1, title="T")
        assert ch.preferred_llm is None
        data = ch.to_mongo()
        assert "preferred_llm" not in data

    def test_chapter_preferred_llm_persisted_when_set(self):
        """preferred_llm is included in to_mongo() when explicitly set."""
        ch = EmbeddedChapter(chapter_no=1, title="T", preferred_llm="gpt-4o")
        data = ch.to_mongo()
        assert data["preferred_llm"] == "gpt-4o"

    def test_chapter_no_raw_title_field(self):
        """EmbeddedChapter must not define raw_title."""
        ch = EmbeddedChapter(chapter_no=1, title="T")
        assert not hasattr(ch, "raw_title")
        data = ch.to_mongo()
        assert "raw_title" not in data

    def test_chapter_legacy_raw_title_ignored_on_deserialize(self):
        """Old Mongo records with raw_title still deserialise (extra='ignore')."""
        ch = EmbeddedChapter.model_validate({
            "chapter_no": 1,
            "title": "T",
            "raw_title": "Old Title",  # legacy field — should be silently ignored
            "preferred_llm": "claude-3",
        })
        assert not hasattr(ch, "raw_title")
        assert ch.preferred_llm == "claude-3"
        assert ch.title == "T"
