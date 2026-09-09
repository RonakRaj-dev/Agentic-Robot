"""MongoDB-backed PipelineError service."""
from __future__ import annotations

from typing import Any, Optional

from db.models.pipeline import PipelineError
from interfaces.pipeline_error_service import IPipelineErrorService
from repos.mongo.pipeline_repo import PipelineErrorRepository
from utils.oid_utils import to_oid


class MongoPipelineErrorService(IPipelineErrorService):
    """Concrete PipelineError service backed by MongoDB."""

    def __init__(self, error_repo: Optional[PipelineErrorRepository] = None) -> None:
        self._repo = error_repo or PipelineErrorRepository()

    async def record_error(
        self,
        pipeline_run_id: str,
        stage: str,
        error_code: str,
        error_message: Optional[str] = None,
        component: Optional[str] = None,
        input_reference: Optional[str] = None,
        is_fatal: bool = False,
        stack_trace: Optional[str] = None,
    ) -> str:
        # ``stage`` is stored as a plain str so free-form stage names
        # from the ingestion pipeline (e.g. "pdf_validation",
        # "page_processing") don't raise ValueError against the
        # PipelineStage enum.
        error = PipelineError(
            pipeline_run_id=to_oid(pipeline_run_id),
            stage=stage,
            error_code=error_code,
            error_message=error_message,
            component=component,
            input_reference=input_reference,
            is_fatal=is_fatal,
            stack_trace=stack_trace,
        )
        inserted = await self._repo.insert(error)
        return str(inserted)

    async def list_errors(self, run_id: str) -> list[PipelineError]:
        return await self._repo.find_by_run(to_oid(run_id))

    async def list_fatal_errors(self, run_id: str) -> list[PipelineError]:
        return await self._repo.find_fatal(to_oid(run_id))
