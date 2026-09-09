"""Ingestion error service interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class IIngestionErrorService(ABC):
    """Ingestion-pipeline error log."""

    @abstractmethod
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
        """Persist a single ingestion error. Returns the new error_id."""
        ...

    @abstractmethod
    async def list_errors(self, job_id: str) -> list[Any]:
        """Return all errors for a given job."""
        ...

    @abstractmethod
    async def list_fatal_errors(self, job_id: str) -> list[Any]:
        """Return only fatal errors for a given job."""
        ...
