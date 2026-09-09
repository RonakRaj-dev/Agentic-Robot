"""Result models for the ingestion pipeline.

The :class:`IngestionResult` carries the outcome of one
``ingest_chapter`` or ``ingest`` call: status, page counts, per-page
results, and any errors.  The legacy ``page_media_asset_ids`` list and
``PageProcessingResult.media_asset_id`` field were removed (neither
was ever populated).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field


class PipelineStatus(str, Enum):
    """Status of an ingestion run (in-memory result, not the DB row).

    Note: this is distinct from :class:`db.models.pipeline.PipelineStatus`
    which is the DB-row status for generation-pipeline runs.  The two
    enums serve different layers and intentionally have different
    values.
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"


class IngestionErrorRecord(BaseModel):
    """Pydantic model representing a pipeline error record (not the exception)."""

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()},
    )
    stage: str = Field(...)
    page_number: Optional[int] = Field(None)
    error_type: str = Field(...)
    error_message: str = Field(...)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PageProcessingResult(BaseModel):
    """Per-page outcome of the page-processing stage.

    ``extracted_text_id`` is the ObjectId of the PAGE_IMAGE
    ``EmbeddedObject`` appended to ``chapter.objects[]``.  For batched
    writes it is back-filled after the ``$push + $each`` returns.
    """

    page_number: int
    success: bool
    extracted_text_id: Optional[str] = None
    error: Optional[IngestionErrorRecord] = None
    processing_time_ms: Optional[float] = None


class IngestionResult(BaseModel):
    """Outcome of one ``ingest_chapter`` or ``ingest`` call."""

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat() if v else None},
        use_enum_values=True,
    )
    book_id: Optional[str] = Field(None)
    chapter_ids: List[str] = Field(default_factory=list)
    pdf_media_asset_id: Optional[str] = Field(None)
    pages_processed: int = Field(0, ge=0)
    pages_failed: int = Field(0, ge=0)
    total_pages: int = Field(0, ge=0)
    processing_time_seconds: float = Field(0.0, ge=0.0)
    pipeline_status: PipelineStatus = Field(default=PipelineStatus.PENDING)
    errors: List[IngestionErrorRecord] = Field(default_factory=list)
    page_results: List[PageProcessingResult] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    def add_error(self, error: IngestionErrorRecord) -> None:
        self.errors.append(error)
        if self.pipeline_status not in (PipelineStatus.FAILED, PipelineStatus.PARTIAL_SUCCESS):
            self.pipeline_status = PipelineStatus.PARTIAL_SUCCESS

    def mark_completed(self) -> None:
        self.completed_at = datetime.now(timezone.utc)
        if not self.errors:
            self.pipeline_status = PipelineStatus.COMPLETED
        elif self.pages_processed > 0:
            self.pipeline_status = PipelineStatus.PARTIAL_SUCCESS
        else:
            self.pipeline_status = PipelineStatus.FAILED

    @property
    def success_rate(self) -> float:
        if self.total_pages == 0:
            return 0.0
        return (self.pages_processed / self.total_pages) * 100
