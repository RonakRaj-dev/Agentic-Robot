from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================================
# Assessment Models
# ============================================================

class AssessmentOption(BaseModel):
    key: str
    text: str


class AssessmentQuestion(BaseModel):
    question_id: str
    type: str
    question_text: str
    correct_answer: str
    explanation: str
    difficulty: str
    options: Optional[
        List[AssessmentOption]
    ] = None


class AssessmentResponse(BaseModel):
    questions: List[
        AssessmentQuestion
    ] = Field(default_factory=list)

    score: Optional[float] = None

    weak_topics: List[str] = Field(
        default_factory=list
    )

    suggested_reading: List[str] = Field(
        default_factory=list
    )

    revision_plan: str = ""


# ============================================================
# Generic Agent Result
# ============================================================

class AgentResult(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    execution_time: float = 0.0


# ============================================================
# Content Utility
# ============================================================

def get_content_str(value: Any) -> str:

    if value is None:
        return ""

    if isinstance(value, str):
        return value

    if isinstance(value, dict):
        return str(
            value.get("content", "")
        )

    if hasattr(value, "content"):
        return str(value.content)

    return str(value)