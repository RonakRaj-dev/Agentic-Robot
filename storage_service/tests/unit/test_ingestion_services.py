"""Unit tests: IngestionJobService and IngestionErrorService."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


# ── IngestionJobService ──────────────────────────────────────────────


async def test_create_job_returns_id_and_running_status(in_memory_services):
    svc = in_memory_services.ingestion_job_service
    job_id = await svc.create_job(book_id="book_001", pipeline_version="v3")
    assert isinstance(job_id, str)
    job = await svc.get_job(job_id)
    assert job is not None
    assert job["status"] == "running"
    assert job["book_id"] == "book_001"
    assert job["pipeline_version"] == "v3"
    assert job["started_at"] is not None
    assert job["completed_at"] is None


async def test_update_progress_accumulates_counters(in_memory_services):
    svc = in_memory_services.ingestion_job_service
    job_id = await svc.create_job(book_id="book_001")
    await svc.update_progress(job_id, pdf_parsed=2)
    await svc.update_progress(job_id, pdf_parsed=1, images_extracted=10)
    job = await svc.get_job(job_id)
    assert job["pdf_parsed"] == 3
    assert job["images_extracted"] == 10


async def test_complete_job(in_memory_services):
    svc = in_memory_services.ingestion_job_service
    job_id = await svc.create_job(book_id="book_001")
    ok = await svc.complete_job(job_id)
    assert ok is True
    job = await svc.get_job(job_id)
    assert job["status"] == "completed"
    assert job["completed_at"] is not None


async def test_fail_job(in_memory_services):
    svc = in_memory_services.ingestion_job_service
    job_id = await svc.create_job(book_id="book_001")
    ok = await svc.fail_job(job_id)
    assert ok is True
    job = await svc.get_job(job_id)
    assert job["status"] == "failed"
    assert job["completed_at"] is not None


# ── IngestionErrorService ────────────────────────────────────────────


async def test_record_error_returns_id(in_memory_services):
    svc = in_memory_services.ingestion_error_service
    err_id = await svc.record_error(
        ingestion_job_id="job_001",
        stage="pdf_parse",
        error_code="E001",
        error_message="boom",
        page_no=5,
        is_fatal=True,
    )
    assert isinstance(err_id, str)


async def test_list_errors_filters_by_job(in_memory_services):
    svc = in_memory_services.ingestion_error_service
    await svc.record_error("job_001", "pdf_parse", "E1")
    await svc.record_error("job_001", "media_extract", "E2")
    await svc.record_error("job_002", "pdf_parse", "E3")
    errors = await svc.list_errors("job_001")
    assert len(errors) == 2
    for e in errors:
        assert e["ingestion_job_id"] == "job_001"


async def test_list_fatal_errors(in_memory_services):
    svc = in_memory_services.ingestion_error_service
    await svc.record_error("job_001", "s1", "E1", is_fatal=False)
    await svc.record_error("job_001", "s2", "E2", is_fatal=True)
    fatal = await svc.list_fatal_errors("job_001")
    assert len(fatal) == 1
    assert fatal[0]["is_fatal"] is True
