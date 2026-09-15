"""Unit tests: ExamService (in-memory implementation).

Verifies the create → update → store_outputs → list lifecycle and
that status transitions work as expected.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_create_exam_returns_id_and_draft_status(in_memory_services):
    svc = in_memory_services.exam_service
    exam_id = await svc.create_exam(
        book_id="book_001",
        title="Class 10 Maths Midterm",
        chapter_ids=["ch_1", "ch_2"],
        duration_minutes=180,
    )
    assert isinstance(exam_id, str)
    exam = await svc.get_exam(exam_id)
    assert exam is not None
    assert exam["title"] == "Class 10 Maths Midterm"
    assert exam["status"] == "draft"
    assert exam["book_id"] == "book_001"
    assert exam["duration_minutes"] == 180


async def test_update_exam_status(in_memory_services):
    svc = in_memory_services.exam_service
    exam_id = await svc.create_exam(
        book_id="book_001", title="T", chapter_ids=[], duration_minutes=60,
    )
    ok = await svc.update_exam_status(exam_id, "approved")
    assert ok is True
    exam = await svc.get_exam(exam_id)
    assert exam["status"] == "approved"


async def test_update_exam_status_unknown_exam_returns_false(in_memory_services):
    svc = in_memory_services.exam_service
    ok = await svc.update_exam_status("does-not-exist", "approved")
    assert ok is False


async def test_store_exam_outputs_sets_uris_and_transitions_to_generated(in_memory_services):
    """v6: ``store_exam_outputs`` now accepts structured ``(bucket, object_key)``
    pairs instead of URL strings.
    """
    svc = in_memory_services.exam_service
    exam_id = await svc.create_exam(
        book_id="book_001", title="T", chapter_ids=[], duration_minutes=60,
    )
    ok = await svc.store_exam_outputs(
        exam_id=exam_id,
        questions_only_bucket="ncert-rag",
        questions_only_object_key="exports/e1/questions_only.pdf",
        questions_with_answers_bucket="ncert-rag",
        questions_with_answers_object_key="exports/e1/qa.pdf",
        total_marks=80,
        question_count=20,
        difficulty_distribution={"easy": 6, "medium": 10, "hard": 4},
        qa_bundle={"questions": []},
    )
    assert ok is True
    exam = await svc.get_exam(exam_id)
    assert exam["status"] == "generated"
    assert exam["total_marks"] == 80
    assert exam["question_count"] == 20
    # v6: structured storage refs are populated.
    assert exam["outputs"]["questions_only_bucket"] == "ncert-rag"
    assert exam["outputs"]["questions_only_object_key"].endswith("questions_only.pdf")
    assert exam["outputs"]["questions_with_answers_bucket"] == "ncert-rag"
    assert exam["outputs"]["questions_with_answers_object_key"].endswith("qa.pdf")
    # v6: legacy URL string fields are None for new records.
    assert exam["outputs"]["questions_only"] is None
    assert exam["outputs"]["questions_with_answers"] is None
    assert exam["difficulty_distribution"] == {"easy": 6, "medium": 10, "hard": 4}
    assert exam["qa_bundle"] == {"questions": []}
    assert exam["generated_at"] is not None


async def test_list_exams_by_book(in_memory_services):
    svc = in_memory_services.exam_service
    await svc.create_exam("book_001", "T1", [], 60)
    await svc.create_exam("book_001", "T2", [], 60)
    await svc.create_exam("book_002", "T3", [], 60)
    exams = await svc.list_exams_by_book("book_001")
    assert len(exams) == 2
    for e in exams:
        assert e["book_id"] == "book_001"
