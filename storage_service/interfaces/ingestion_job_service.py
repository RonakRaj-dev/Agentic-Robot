"""Ingestion job service interface.

Tracks one execution of the ingestion pipeline (PDF → chapters → page
images).  In the MVP, ingestion is manual so this collection is
sparsely populated, but the interface is provided for when ingestion
is automated (post-MVP).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class IIngestionJobService(ABC):
    """Ingestion-pipeline job observability."""

    @abstractmethod
    async def create_job(
        self,
        book_id: str,
        pipeline_version: Optional[str] = None,
    ) -> str:
        """Create a new IngestionJob in RUNNING status. Returns job_id."""
        ...

    @abstractmethod
    async def get_job(self, job_id: str) -> Optional[Any]:
        """Return the IngestionJob document, or None."""
        ...

    @abstractmethod
    async def update_progress(
        self,
        job_id: str,
        pdf_parsed: Optional[int] = None,
        images_extracted: Optional[int] = None,
    ) -> bool:
        """Increment progress counters atomically (``$inc``)."""
        ...

    @abstractmethod
    async def complete_job(self, job_id: str) -> bool:
        """Mark the job as COMPLETED and stamp ``completed_at``."""
        ...

    @abstractmethod
    async def fail_job(self, job_id: str) -> bool:
        """Mark the job as FAILED and stamp ``completed_at``."""
        ...
