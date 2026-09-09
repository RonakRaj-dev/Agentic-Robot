from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class AssessmentContext:
    session_id: str = "default_sess"
    student_id: str = "default_student"
    grade: int = 5
    subject: str = "General"
    action: str = "generate"
    student_answers: Dict[str, Any] | None = None
    original_questions: list | None = None

    @classmethod
    def from_input(cls, x: Any) -> "AssessmentContext":
        metadata = cls._extract_metadata(x)

        return cls(
            session_id=metadata.get("session_id", "default_sess"),
            student_id=(
                metadata.get("student_id")
                or metadata.get("username")
                or "default_student"
            ),
            grade=metadata.get("grade", 5),
            subject=metadata.get("subject", "General"),
            action=metadata.get("action", "generate"),
            student_answers=metadata.get("student_answers", {}),
            original_questions=metadata.get("original_questions", []),
        )

    @staticmethod
    def _extract_metadata(x: Any) -> Dict[str, Any]:
        if isinstance(x, dict):
            return x.get("metadata", {}) or {}

        return getattr(x, "metadata", {}) or {}