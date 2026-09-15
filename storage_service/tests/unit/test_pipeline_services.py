"""Unit tests: PipelineRunService and PipelineErrorService."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


# ── PipelineRunService ────────────────────────────────────────────────


async def test_create_run_returns_id_and_running_status(in_memory_services):
    svc = in_memory_services.pipeline_run_service
    run_id = await svc.create_run(book_id="book_001", pipeline_version="v3")
    assert isinstance(run_id, str)
    run = await svc.get_run(run_id)
    assert run is not None
    assert run["status"] == "running"
    assert run["book_id"] == "book_001"
    assert run["pipeline_version"] == "v3"
    assert run["started_at"] is not None
    assert run["completed_at"] is None


async def test_update_progress_accumulates_counters(in_memory_services):
    svc = in_memory_services.pipeline_run_service
    run_id = await svc.create_run(book_id="book_001")
    await svc.update_progress(run_id, processed_pages=5)
    await svc.update_progress(run_id, processed_pages=3, total_questions_generated=10)
    run = await svc.get_run(run_id)
    assert run["processed_pages"] == 8
    assert run["total_questions_generated"] == 10


async def test_update_stage(in_memory_services):
    svc = in_memory_services.pipeline_run_service
    run_id = await svc.create_run(book_id="book_001")
    ok = await svc.update_stage(run_id, "generator")
    assert ok is True
    run = await svc.get_run(run_id)
    assert run["current_stage"] == "generator"


async def test_complete_run(in_memory_services):
    svc = in_memory_services.pipeline_run_service
    run_id = await svc.create_run(book_id="book_001")
    ok = await svc.complete_run(run_id)
    assert ok is True
    run = await svc.get_run(run_id)
    assert run["status"] == "completed"
    assert run["completed_at"] is not None


async def test_fail_run(in_memory_services):
    svc = in_memory_services.pipeline_run_service
    run_id = await svc.create_run(book_id="book_001")
    ok = await svc.fail_run(run_id)
    assert ok is True
    run = await svc.get_run(run_id)
    assert run["status"] == "failed"
    assert run["completed_at"] is not None


# ── PipelineErrorService ─────────────────────────────────────────────


async def test_record_error_returns_id(in_memory_services):
    svc = in_memory_services.pipeline_error_service
    err_id = await svc.record_error(
        pipeline_run_id="run_001",
        stage="pdf_processor",
        error_code="E001",
        error_message="boom",
        component="PdfProcessor",
        is_fatal=True,
    )
    assert isinstance(err_id, str)


async def test_list_errors_filters_by_run(in_memory_services):
    svc = in_memory_services.pipeline_error_service
    await svc.record_error("run_001", "pdf_processor", "E1")
    await svc.record_error("run_001", "generator", "E2")
    await svc.record_error("run_002", "generator", "E3")
    errors = await svc.list_errors("run_001")
    assert len(errors) == 2
    for e in errors:
        assert e["pipeline_run_id"] == "run_001"


async def test_list_fatal_errors(in_memory_services):
    svc = in_memory_services.pipeline_error_service
    await svc.record_error("run_001", "s1", "E1", is_fatal=False)
    await svc.record_error("run_001", "s2", "E2", is_fatal=True)
    await svc.record_error("run_001", "s3", "E3", is_fatal=True)
    fatal = await svc.list_fatal_errors("run_001")
    assert len(fatal) == 2
    for e in fatal:
        assert e["is_fatal"] is True
