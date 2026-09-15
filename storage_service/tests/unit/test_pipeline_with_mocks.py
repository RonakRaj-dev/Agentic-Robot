"""Unit tests: pipeline runs end-to-end against mock services.

Schema v3 — PyMuPDF only, PAGE_IMAGE objects, chapter PDF refs,
processed_pages counter.
"""
from __future__ import annotations

import asyncio
import json
import logging

import pytest

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
pytestmark = pytest.mark.asyncio


async def test_pipeline_completes_successfully(
    in_memory_pipeline, sample_ingestion_input
):
    pipeline, services = in_memory_pipeline
    result = await pipeline.ingest(sample_ingestion_input)
    assert result.pipeline_status == "completed", (
        f"Expected completed, got {result.pipeline_status}; errors={result.errors}"
    )
    assert result.total_pages == 3
    assert result.pages_processed == 3
    assert result.pages_failed == 0
    assert result.success_rate == 100.0
    assert result.book_id is not None
    assert result.pdf_media_asset_id is not None
    assert len(result.chapter_ids) >= 1
    assert all(p.success for p in result.page_results)
    assert [p.page_number for p in result.page_results] == [1, 2, 3]
    assert all(p.extracted_text_id for p in result.page_results)


async def test_storage_received_chapter_pdf_and_page_images(
    in_memory_pipeline, sample_ingestion_input
):
    pipeline, services = in_memory_pipeline
    await pipeline.ingest(sample_ingestion_input)
    storage = services["storage"]
    # 1 source PDF + 1 chapter PDF + 3 page PNGs
    assert storage.total_objects >= 5


async def test_book_persistence_with_embedded_chapters(
    in_memory_pipeline, sample_ingestion_input
):
    pipeline, services = in_memory_pipeline
    await pipeline.ingest(sample_ingestion_input)
    books = services["books"].all_books
    assert len(books) == 1
    book = books[0]
    assert book["title"] == "NCERT Class 8 Science Sample"
    assert book["class_level"] == "8"
    assert book["subject"] == "Science"
    assert book["board"] == "NCERT"
    assert book["total_pages"] == 3

    chapters = book["chapters"]
    assert len(chapters) >= 1

    # Each chapter's objects[] should contain one PAGE_IMAGE per page.
    total_objects = sum(len(c["objects"]) for c in chapters)
    assert total_objects == 3  # one PAGE_IMAGE per page


async def test_chapter_has_pdf_reference(
    in_memory_pipeline, sample_ingestion_input
):
    """Verify chapter stores full PDF reference directly.

    v6: ``pdf_object_url`` is no longer written — only
    ``pdf_object_key`` + ``pdf_bucket_name`` + ``pdf_size_bytes``.
    """
    pipeline, services = in_memory_pipeline
    await pipeline.ingest(sample_ingestion_input)
    book = services["books"].all_books[0]
    for ch in book["chapters"]:
        assert ch["pdf_object_key"] is not None
        assert ch["pdf_bucket_name"] is not None
        # v6: pdf_object_url is None for new uploads.
        assert ch.get("pdf_object_url") is None
        assert ch["pdf_size_bytes"] is not None
        assert ch["pdf_size_bytes"] > 0


async def test_chapter_has_processed_pages_counter(
    in_memory_pipeline, sample_ingestion_input
):
    """Verify processed_pages counter is updated."""
    pipeline, services = in_memory_pipeline
    await pipeline.ingest(sample_ingestion_input)
    book = services["books"].all_books[0]
    for ch in book["chapters"]:
        assert ch["processed_pages"] == 3


async def test_page_objects_are_page_images_with_text(
    in_memory_pipeline, sample_ingestion_input
):
    """Verify objects[] contains PAGE_IMAGE entries with text metadata.

    v6: ``object_url`` is no longer written for new uploads — only
    ``bucket_name`` + ``object_key``.  The legacy ``object_url`` field
    is allowed to be present (None) but is not asserted on.
    """
    pipeline, services = in_memory_pipeline
    await pipeline.ingest(sample_ingestion_input)
    book = services["books"].all_books[0]
    all_objects = [
        obj for ch in book["chapters"] for obj in ch["objects"]
    ]
    assert len(all_objects) == 3
    for obj in all_objects:
        assert obj["object_type"] == "PAGE_IMAGE"
        assert obj["mime_type"] == "image/png"
        assert "object_key" in obj
        assert "bucket_name" in obj
        # v6: object_url may be present (None) but is no longer
        # populated for new uploads.
        assert obj.get("object_url") is None
        assert isinstance(obj["page_no"], int)
        assert isinstance(obj["size_bytes"], int)
        # Text metadata lives in metadata field
        assert "metadata" in obj
        assert "plain_text" in obj["metadata"]
        assert "word_count" in obj["metadata"]
        assert "token_count" in obj["metadata"]
        assert obj["metadata"]["extraction_method"] == "pymupdf"


async def test_no_page_pdf_objects_in_storage(
    in_memory_pipeline, sample_ingestion_input
):
    """Verify no PAGE_PDF objects exist — only PAGE_IMAGE."""
    pipeline, services = in_memory_pipeline
    await pipeline.ingest(sample_ingestion_input)
    book = services["books"].all_books[0]
    for ch in book["chapters"]:
        for obj in ch["objects"]:
            assert obj["object_type"] != "PAGE_PDF"
            assert obj["object_type"] == "PAGE_IMAGE"


async def test_pipeline_handles_corrupt_pdf(in_memory_pipeline, tmp_path):
    from models.ingestion_input import IngestionInput, BookMetadata

    pipeline, services = in_memory_pipeline
    bad_pdf = tmp_path / "bad.pdf"
    bad_pdf.write_bytes(b"not a real pdf file")
    input_data = IngestionInput(
        pdf_path=bad_pdf,
        book_metadata=BookMetadata(title="Bad PDF"),
        class_level="8",
        subject="Science",
    )
    result = await pipeline.ingest(input_data)
    assert result.pipeline_status == "failed"
    assert len(result.errors) >= 1


async def test_pipeline_result_serialises_to_json(
    in_memory_pipeline, sample_ingestion_input
):
    pipeline, services = in_memory_pipeline
    result = await pipeline.ingest(sample_ingestion_input)
    payload = result.model_dump_json()
    parsed = json.loads(payload)
    assert parsed["pipeline_status"] == "completed"
    assert parsed["total_pages"] == 3
    assert parsed["pages_processed"] == 3
    assert len(parsed["page_results"]) == 3


async def test_real_service_classes_import_cleanly():
    """Ensure all real services import cleanly and conform to interfaces."""
    from services.storage.storage_adapter import MinioStorageServiceAdapter
    from services.mongo.book_service import MongoBookService
    from services.pymupdf.pymupdf_service import PyMuPDFService
    from interfaces.book_service import IBookService
    from interfaces.pymupdf_service import IPyMuPDFService
    from interfaces.storage_service import IStorageService
    assert issubclass(MinioStorageServiceAdapter, IStorageService)
    assert issubclass(MongoBookService, IBookService)
    assert issubclass(PyMuPDFService, IPyMuPDFService)
