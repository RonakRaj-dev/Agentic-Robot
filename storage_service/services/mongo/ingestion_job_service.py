"""MongoDB-backed IngestionJob service."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from db.models.ingestion import IngestionJob, IngestionStatus
from interfaces.ingestion_job_service import IIngestionJobService
from repos.mongo.ingestion_repo import IngestionJobRepository
from utils.oid_utils import to_oid


class MongoIngestionJobService(IIngestionJobService):
    """Concrete IngestionJob service backed by MongoDB."""

    def __init__(self, job_repo: Optional[IngestionJobRepository] = None) -> None:
        self._repo = job_repo or IngestionJobRepository()

    async def create_job(
        self,
        book_id: str,
        pipeline_version: Optional[str] = None,
    ) -> str:
        job = IngestionJob(
            book_id=to_oid(book_id),
            status=IngestionStatus.RUNNING,
            pipeline_version=pipeline_version,
            started_at=datetime.now(timezone.utc),
        )
        inserted = await self._repo.insert(job)
        return str(inserted)

    async def get_job(self, job_id: str) -> Optional[IngestionJob]:
        return await self._repo.find_by_id(job_id)

    async def update_progress(
        self,
        job_id: str,
        pdf_parsed: Optional[int] = None,
        images_extracted: Optional[int] = None,
    ) -> bool:
        """Increment progress counters atomically via ``$inc``.

        Goes through ``BaseMongoRepository.increment_fields`` so the
        service never touches ``self._repo._col`` directly.
        """
        inc: dict[str, int] = {}
        if pdf_parsed is not None:
            inc["pdf_parsed"] = pdf_parsed
        if images_extracted is not None:
            inc["images_extracted"] = images_extracted
        if not inc:
            return True
        return await self._repo.increment_fields(to_oid(job_id), inc)

    async def complete_job(self, job_id: str) -> bool:
        return await self._repo.update(job_id, {
            "status": IngestionStatus.COMPLETED.value,
            "completed_at": datetime.now(timezone.utc),
        })

    async def fail_job(self, job_id: str) -> bool:
        return await self._repo.update(job_id, {
            "status": IngestionStatus.FAILED.value,
            "completed_at": datetime.now(timezone.utc),
        })
