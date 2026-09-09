"""Exam service interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class IExamService(ABC):
    """Finalized exam lifecycle.

    An Exam document records the request config that produced it, the
    realized question count + difficulty distribution, and the two
    output URIs (questions-only + questions-with-answers) in object
    storage.
    """

    @abstractmethod
    async def create_exam(
        self,
        book_id: str,
        title: str,
        chapter_ids: list[str],
        duration_minutes: int,
        request_config: Optional[dict[str, Any]] = None,
        pipeline_run_id: Optional[str] = None,
    ) -> str:
        """Create a new Exam document in DRAFT status.

        Returns the new exam_id.
        """
        ...

    @abstractmethod
    async def get_exam(self, exam_id: str) -> Optional[Any]:
        """Return the Exam document, or None."""
        ...

    @abstractmethod
    async def update_exam_status(
        self,
        exam_id: str,
        status: str,
    ) -> bool:
        """Transition the exam to a new status (draft→generated→approved→published)."""
        ...

    @abstractmethod
    async def store_exam_outputs(
        self,
        exam_id: str,
        total_marks: int,
        question_count: int,
        questions_only_bucket: Optional[str] = None,
        questions_only_object_key: Optional[str] = None,
        questions_with_answers_bucket: Optional[str] = None,
        questions_with_answers_object_key: Optional[str] = None,
        difficulty_distribution: Optional[dict[str, int]] = None,
        qa_bundle: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Persist the two rendered output storage refs and finalize counts.

        As of v6, outputs are stored as structured ``(bucket, object_key)``
        pairs rather than URL strings.  Callers that need an access URL
        for a stored output must request one via
        :meth:`IStorageService.get_public_url`.

        Also transitions the exam to GENERATED status.

        .. versionchanged:: v6
            Replaced ``questions_only_uri`` / ``questions_with_answers_uri``
            (URL strings) with the four structured fields
            ``questions_only_bucket`` / ``questions_only_object_key`` /
            ``questions_with_answers_bucket`` /
            ``questions_with_answers_object_key``.

        .. versionchanged:: v7
            Presigned URL generation has been removed.  Access URLs are
            now built directly by :meth:`IStorageService.get_public_url`
            from ``Settings.public_storage_url``.
        """
        ...

    @abstractmethod
    async def list_exams_by_book(self, book_id: str) -> list[Any]:
        """Return all exams for a given book."""
        ...
