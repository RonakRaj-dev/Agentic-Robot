"""Unit tests: ServiceRegistry (DI container).

Verifies that the factory assembles all 10 services with the correct
interface types, and that the InMemoryBookService and
InMemoryObjectService share the same underlying state (object service
is a facade over book service).
"""
from __future__ import annotations

import pytest

from factory import ServiceRegistry, build_in_memory_registry


def test_build_in_memory_registry_returns_all_services():
    reg = build_in_memory_registry()
    assert isinstance(reg, ServiceRegistry)
    # All 10 services must be present.
    assert reg.book_service is not None
    assert reg.object_service is not None
    assert reg.exam_service is not None
    assert reg.pipeline_run_service is not None
    assert reg.pipeline_error_service is not None
    assert reg.ingestion_job_service is not None
    assert reg.ingestion_error_service is not None
    assert reg.config_service is not None
    assert reg.storage_service is not None
    assert reg.pymupdf_service is not None


def test_registry_services_implement_interfaces():
    reg = build_in_memory_registry()
    from interfaces.book_service import IBookService
    from interfaces.config_service import IConfigService
    from interfaces.exam_service import IExamService
    from interfaces.ingestion_error_service import IIngestionErrorService
    from interfaces.ingestion_job_service import IIngestionJobService
    from interfaces.object_service import IObjectService
    from interfaces.pipeline_error_service import IPipelineErrorService
    from interfaces.pipeline_run_service import IPipelineRunService
    from interfaces.pymupdf_service import IPyMuPDFService
    from interfaces.storage_service import IStorageService

    assert isinstance(reg.book_service, IBookService)
    assert isinstance(reg.object_service, IObjectService)
    assert isinstance(reg.exam_service, IExamService)
    assert isinstance(reg.pipeline_run_service, IPipelineRunService)
    assert isinstance(reg.pipeline_error_service, IPipelineErrorService)
    assert isinstance(reg.ingestion_job_service, IIngestionJobService)
    assert isinstance(reg.ingestion_error_service, IIngestionErrorService)
    assert isinstance(reg.config_service, IConfigService)
    assert isinstance(reg.storage_service, IStorageService)
    assert isinstance(reg.pymupdf_service, IPyMuPDFService)


@pytest.mark.asyncio
async def test_object_service_shares_state_with_book_service():
    """ObjectService is a facade over BookService — writes through one
    must be visible to the other.

    v6: ``object_url`` is optional on ``append_page_image`` — omitted here.
    """
    reg = build_in_memory_registry()
    book_id = await reg.book_service.create_book(
        title="T", class_level="8", subject="Science", language="en",
        board="NCERT", metadata={}, pdf_asset_id="", total_pages=0,
    )
    chapter_id = await reg.book_service.add_chapter(
        book_id=book_id, chapter_no=1, title="Ch 1",
    )
    # Write through ObjectService.
    await reg.object_service.append_page_image(
        book_id=book_id, chapter_id=chapter_id, page_no=1,
        object_key="k", bucket_name="b", size_bytes=1,
    )
    # Read through BookService.
    book = await reg.book_service.get_book(book_id)
    chapters = book["chapters"] if isinstance(book, dict) else book.chapters
    assert len(chapters[0]["objects"]) == 1
