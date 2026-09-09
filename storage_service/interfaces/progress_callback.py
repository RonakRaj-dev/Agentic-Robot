"""Progress callback interface for pipeline observability."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class IProgressCallback(ABC):
    @abstractmethod
    async def on_stage_start(
        self, stage: str, message: str, total_items: Optional[int] = None
    ) -> None:
        ...

    @abstractmethod
    async def on_progress(
        self,
        stage: str,
        current: int,
        total: int,
        message: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        ...

    @abstractmethod
    async def on_stage_complete(
        self, stage: str, message: str, result: Optional[Any] = None
    ) -> None:
        ...

    @abstractmethod
    async def on_error(
        self, stage: str, error: Exception, page_number: Optional[int] = None
    ) -> None:
        ...
