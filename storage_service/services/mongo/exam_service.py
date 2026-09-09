"""MongoDB-backed Exam service."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from db.models.exam import Exam, ExamStatus
from interfaces.exam_service import IExamService
from repos.mongo.exam_repo import ExamRepository
from utils.oid_utils import to_oid


class MongoExamService(IExamService):
    """Concrete Exam service backed by MongoDB."""

    def __init__(self, exam_repo: Optional[ExamRepository] = None) -> None:
        self._repo = exam_repo or ExamRepository()

    async def create_exam(
        self,
        book_id: str,
        title: str,
        chapter_ids: list[str],
        duration_minutes: int,
        request_config: Optional[dict[str, Any]] = None,
        pipeline_run_id: Optional[str] = None,
    ) -> str:
        exam = Exam(
            book_id=to_oid(book_id),
            title=title,
            chapter_ids=[to_oid(c) for c in chapter_ids],
            duration_minutes=duration_minutes,
            status=ExamStatus.DRAFT,
            pipeline_run_id=to_oid(pipeline_run_id) if pipeline_run_id else None,
            request_config=request_config,
            generator_version=(
                str(request_config.get("version")) if request_config else None
            ),
        )
        inserted = await self._repo.insert(exam)
        return str(inserted)

    async def get_exam(self, exam_id: str) -> Optional[Exam]:
        return await self._repo.find_by_id(exam_id)

    async def update_exam_status(
        self,
        exam_id: str,
        status: str,
    ) -> bool:
        return await self._repo.update(exam_id, {"status": status})

    async def store_exam_outputs(
        self,
        exam_id: str,
        total_marks: int,
        question_count: int,
        questions_only_bucket: Optional[str] = None,
        questions_only_object_key: Optional[str] = None,
        questions_with_answers_bucket: Optional[str] = None,
        questions_with_answers_object_key: Optional[str] = None,
        difficulty_distribution: Optional[dict[str, int]] = None,
        qa_bundle: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Persist the two rendered output storage refs and finalize counts.

        .. versionchanged:: v6
            Outputs are now stored as structured ``(bucket, object_key)``
            pairs.  The legacy ``questions_only`` / ``questions_with_answers``
            string URL fields on :class:`ExamOutputs` are left as
            ``None`` — they are only populated on old records (and by
            the migration script's back-fill of legacy records).

        .. versionchanged:: v7
            Presigned URL generation has been removed.  Access URLs are
            built on demand via :meth:`IStorageService.get_public_url`
            from ``Settings.public_storage_url``.
        """
        from db.models.exam import DifficultyDistribution, ExamOutputs
        outputs = ExamOutputs(
            questions_only_bucket=questions_only_bucket,
            questions_only_object_key=questions_only_object_key,
            questions_with_answers_bucket=questions_with_answers_bucket,
            questions_with_answers_object_key=questions_with_answers_object_key,
            # v6: do not populate the legacy URL string fields — they
            # are kept as None for new records.
            questions_only=None,
            questions_with_answers=None,
        )
        updates: dict[str, Any] = {
            "total_marks": total_marks,
            "question_count": question_count,
            "status": ExamStatus.GENERATED.value,
            "generated_at": datetime.now(timezone.utc),
            "outputs": outputs.model_dump(),
        }
        if difficulty_distribution:
            updates["difficulty_distribution"] = DifficultyDistribution(
                **difficulty_distribution,
            )
        if qa_bundle:
            updates["qa_bundle"] = qa_bundle
        return await self._repo.update(exam_id, updates)

    async def list_exams_by_book(self, book_id: str) -> list[Exam]:
        return await self._repo.find_by_book(to_oid(book_id))
