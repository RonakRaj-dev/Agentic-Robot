"""MongoDB-backed PipelineRun service."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from db.models.pipeline import PipelineRun, PipelineStatus
from interfaces.pipeline_run_service import IPipelineRunService
from repos.mongo.pipeline_repo import PipelineRunRepository
from utils.oid_utils import to_oid


class MongoPipelineRunService(IPipelineRunService):
    """Concrete PipelineRun service backed by MongoDB."""

    def __init__(self, run_repo: Optional[PipelineRunRepository] = None) -> None:
        self._repo = run_repo or PipelineRunRepository()

    async def create_run(
        self,
        book_id: str,
        pipeline_version: Optional[str] = None,
    ) -> str:
        run = PipelineRun(
            book_id=to_oid(book_id),
            status=PipelineStatus.RUNNING,
            pipeline_version=pipeline_version,
            started_at=datetime.now(timezone.utc),
        )
        inserted = await self._repo.insert(run)
        return str(inserted)

    async def get_run(self, run_id: str) -> Optional[PipelineRun]:
        return await self._repo.find_by_id(run_id)

    async def update_progress(
        self,
        run_id: str,
        processed_pages: Optional[int] = None,
        total_questions_generated: Optional[int] = None,
        total_exams_generated: Optional[int] = None,
    ) -> bool:
        """Increment progress counters atomically via ``$inc``.

        Goes through ``BaseMongoRepository.increment_fields`` so the
        service never touches ``self._repo._col`` directly.
        """
        inc: dict[str, int] = {}
        if processed_pages is not None:
            inc["processed_pages"] = processed_pages
        if total_questions_generated is not None:
            inc["total_questions_generated"] = total_questions_generated
        if total_exams_generated is not None:
            inc["total_exams_generated"] = total_exams_generated
        if not inc:
            return True
        return await self._repo.increment_fields(to_oid(run_id), inc)

    async def update_stage(
        self,
        run_id: str,
        stage: str,
    ) -> bool:
        return await self._repo.update(run_id, {
            "current_stage": stage,
        })

    async def complete_run(self, run_id: str) -> bool:
        return await self._repo.update(run_id, {
            "status": PipelineStatus.COMPLETED.value,
            "completed_at": datetime.now(timezone.utc),
        })

    async def fail_run(self, run_id: str) -> bool:
        return await self._repo.update(run_id, {
            "status": PipelineStatus.FAILED.value,
            "completed_at": datetime.now(timezone.utc),
        })
