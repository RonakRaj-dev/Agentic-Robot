"""Pipeline run service interface.

A PipelineRun document tracks one execution of the generation pipeline
(Planner → Generator → Formator).  It records status, current stage,
progress counters, and timestamps.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class IPipelineRunService(ABC):
    """Generation-pipeline run observability."""

    @abstractmethod
    async def create_run(
        self,
        book_id: str,
        pipeline_version: Optional[str] = None,
    ) -> str:
        """Create a new PipelineRun in RUNNING status. Returns run_id."""
        ...

    @abstractmethod
    async def get_run(self, run_id: str) -> Optional[Any]:
        """Return the PipelineRun document, or None."""
        ...

    @abstractmethod
    async def update_progress(
        self,
        run_id: str,
        processed_pages: Optional[int] = None,
        total_questions_generated: Optional[int] = None,
        total_exams_generated: Optional[int] = None,
    ) -> bool:
        """Increment progress counters atomically (``$inc``)."""
        ...

    @abstractmethod
    async def update_stage(
        self,
        run_id: str,
        stage: str,
    ) -> bool:
        """Set the current pipeline stage (e.g. ``planner``, ``generator``)."""
        ...

    @abstractmethod
    async def complete_run(self, run_id: str) -> bool:
        """Mark the run as COMPLETED and stamp ``completed_at``."""
        ...

    @abstractmethod
    async def fail_run(self, run_id: str) -> bool:
        """Mark the run as FAILED and stamp ``completed_at``."""
        ...
