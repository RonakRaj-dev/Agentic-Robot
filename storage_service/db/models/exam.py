from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field
from .base import MongoBase, PyObjectId, istnow
from enum import Enum


class ExamStatus(str, Enum):
    DRAFT = "draft"
    GENERATED = "generated"
    APPROVED = "approved"
    PUBLISHED = "published"


class DifficultyDistribution(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    easy: int = 0
    medium: int = 0
    hard: int = 0


class ExamOutputs(BaseModel):
    """The two rendered output references produced by the Exam Formator.

    Per architecture doc section 9.1, every finalized exam has two
    outputs: a questions-only PDF and a questions-with-answers PDF.

    .. versionchanged:: v6
        The two outputs are now stored as **structured storage refs**
        (``bucket`` + ``object_key``) rather than persistent URL
        strings.  Persistent URLs break when the MinIO endpoint
        changes (localhost, tunnel, k8s service, etc).

        Backward compatibility: the legacy ``questions_only`` and
        ``questions_with_answers`` string fields are retained as
        ``Optional[str]`` so old records still deserialise.  They are
        populated ONLY by old data — new writes leave them as ``None``
        and populate the structured ``*_bucket`` / ``*_object_key``
        fields instead.

        Use :func:`utils.storage_compat.resolve_exam_output_ref` to
        extract ``(bucket, object_key)`` uniformly from old and new
        records.

    .. versionchanged:: v7
        Presigned URL generation has been removed entirely.  The MinIO
        buckets are publicly downloadable; access URLs are built on
        demand by :meth:`IStorageService.get_public_url` from
        ``Settings.public_storage_url``.  No URLs are persisted.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # ── v6 structured storage references (canonical) ─────────────────
    questions_only_bucket: Optional[str] = None
    questions_only_object_key: Optional[str] = None
    questions_with_answers_bucket: Optional[str] = None
    questions_with_answers_object_key: Optional[str] = None

    # ── legacy URL fields (deprecated, kept for backward compat) ─────
    # Populated ONLY on old records.  New writes leave these as None.
    questions_only: Optional[str] = None
    questions_with_answers: Optional[str] = None


class Exam(MongoBase):
    book_id: PyObjectId
    pipeline_run_id: Optional[PyObjectId] = None
    title: str
    chapter_ids: list[PyObjectId] = Field(default_factory=list)
    question_ids: list[PyObjectId] = Field(default_factory=list)

    # The wizard payload (architecture doc 9.2) that produced this exam.
    request_config: Optional[dict[str, Any]] = None

    # Realized Q&A bundle (architecture doc 9.1).
    qa_bundle: Optional[dict[str, Any]] = None

    difficulty_distribution: Optional[DifficultyDistribution] = None
    total_marks: int = 0
    question_count: int = 0
    duration_minutes: int
    status: ExamStatus = ExamStatus.DRAFT
    generator_version: Optional[str] = None

    # Two output refs (questions-only + questions-with-answers).
    # See :class:`ExamOutputs` for the v6 backward-compat strategy.
    outputs: ExamOutputs = Field(default_factory=ExamOutputs)

    generated_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=istnow)

    class Settings:
        collection = "EXAMS"
        indexes = [
            [("book_id", 1)],
            [("pipeline_run_id", 1)],
            [("status", 1)],
        ]
