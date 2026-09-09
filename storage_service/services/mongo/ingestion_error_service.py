"""MongoDB-backed IngestionError service."""
from __future__ import annotations

from typing import Any, Optional

from db.models.ingestion import IngestionError
from interfaces.ingestion_error_service import IIngestionErrorService
from repos.mongo.ingestion_repo import IngestionErrorRepository
from utils.oid_utils import to_oid


class MongoIngestionErrorService(IIngestionErrorService):
    """Concrete IngestionError service backed by MongoDB."""

    def __init__(self, error_repo: Optional[IngestionErrorRepository] = None) -> None:
        self._repo = error_repo or IngestionErrorRepository()

    async def record_error(
        self,
        ingestion_job_id: str,
        stage: str,
        error_code: str,
        error_message: Optional[str] = None,
        page_no: Optional[int] = None,
        is_fatal: bool = False,
        stack_trace: Optional[str] = None,
    ) -> str:
        # ``stage`` is stored as a plain str so free-form stage names
        # from the ingestion pipeline (e.g. "pdf_validation",
        # "page_processing") don't raise ValueError against the
        # IngestionStage enum.
        error = IngestionError(
            ingestion_job_id=to_oid(ingestion_job_id),
            stage=stage,
            error_code=error_code,
            error_message=error_message,
            page_no=page_no,
            is_fatal=is_fatal,
            stack_trace=stack_trace,
        )
        inserted = await self._repo.insert(error)
        return str(inserted)

    async def list_errors(self, job_id: str) -> list[IngestionError]:
        return await self._repo.find_by_job(to_oid(job_id))

    async def list_fatal_errors(self, job_id: str) -> list[IngestionError]:
        return await self._repo.find_fatal(to_oid(job_id))
