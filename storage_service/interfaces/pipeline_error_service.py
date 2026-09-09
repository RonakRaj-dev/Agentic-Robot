"""Pipeline error service interface.

Records per-error diagnostics for generation-pipeline runs: stage,
error_code, component, retry_count, is_fatal, stack_trace.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class IPipelineErrorService(ABC):
    """Generation-pipeline error log."""

    @abstractmethod
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
        """Persist a single pipeline error. Returns the new error_id."""
        ...

    @abstractmethod
    async def list_errors(self, run_id: str) -> list[Any]:
        """Return all errors for a given run, ordered by creation time."""
        ...

    @abstractmethod
    async def list_fatal_errors(self, run_id: str) -> list[Any]:
        """Return only fatal errors for a given run."""
        ...
