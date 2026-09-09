import json
import time
from typing import Any, Dict, List
import models.compat

from agentscope.agent import Agent
from agentscope.message import Msg
from loguru import logger

from ai_teacher_robot.repositories.v3_repositories import (
    ClassroomSessionRepository,
    LearningHistoryRepository,
)
from .. import LLMGateway
from models.schemas import AnalyticsResponse, AgentResult, get_content_str
from state.agentState import AgentStateManager
from .prompts import build_analytics_prompt


class AnalyticsAgent(Agent):
    """
    AnalyticsAgent aggregates student learning history and generates
    classroom/student performance intelligence.
    """

    DEFAULT_SESSION_ID = "default_sess"
    DEFAULT_STUDENT_ID = "default_student"
    DEFAULT_GRADE = 5
    DEFAULT_SUBJECT = "General"

    WEAK_MASTERY_THRESHOLD = 0.6

    def __init__(
        self,
        name: str = "AnalyticsAgent",
        **kwargs: Any,
    ) -> None:
        super().__init__()
        self.name = name

        self.state_manager = AgentStateManager()
        self.history_repo = LearningHistoryRepository()
        self.session_repo = ClassroomSessionRepository()
        from .. import LLMGateway
        self.gateway = LLMGateway()

    async def reply(self, x: Any = None) -> Msg:
        start_time = time.perf_counter()

        try:
            query = get_content_str(x)
            metadata = self._extract_metadata(x)

            session_id = metadata.get(
                "session_id",
                self.DEFAULT_SESSION_ID,
            )

            student_id = self._get_student_id(metadata)
            grade = metadata.get("grade", self.DEFAULT_GRADE)
            subject = metadata.get(
                "subject",
                self.DEFAULT_SUBJECT,
            )

            logger.info(
                f"{self.name} processing analytics request | "
                f"student_id={student_id} | "
                f"session_id={session_id}"
            )

            records = await self._get_learning_history(student_id)
            statistics = self._calculate_statistics(records)

            prompt = build_analytics_prompt(
                query=query,
                student_id=student_id,
                grade=grade,
                subject=subject,
                records=records,
                statistics=statistics,
            )

            parsed_response = await self._generate_response(prompt)
            response = AnalyticsResponse(**parsed_response)

            await self._store_report(
                session_id=session_id,
                response=response,
            )

            execution_time = time.perf_counter() - start_time

            result = AgentResult(
                success=True,
                data=response.model_dump(),
                execution_time=execution_time,
            )

            logger.info(
                f"{self.name} completed successfully | "
                f"student_id={student_id} | "
                f"session_id={session_id} | "
                f"time={execution_time:.3f}s"
            )

            return self._build_message(
                result=result,
                metadata={
                    "agent_result": result.model_dump(),
                    "student_id": student_id,
                    "session_id": session_id,
                },
            )

        except Exception as exc:
            execution_time = time.perf_counter() - start_time

            logger.exception(
                f"{self.name} failed | error={exc}"
            )

            result = AgentResult(
                success=False,
                data=None,
                error=f"Analytics compilation exception: {exc}",
                execution_time=execution_time,
            )

            return self._build_message(
                result=result,
                metadata={
                    "agent_result": result.model_dump(),
                },
            )

    @staticmethod
    def _extract_metadata(x: Any) -> Dict[str, Any]:
        if isinstance(x, dict):
            return x.get("metadata", {}) or {}

        if hasattr(x, "metadata"):
            return getattr(x, "metadata", {}) or {}

        return {}

    def _get_student_id(self, metadata: Dict[str, Any]) -> str:
        return (
            metadata.get("student_id")
            or metadata.get("username")
            or self.DEFAULT_STUDENT_ID
        )

    async def _get_learning_history(self, student_id: str) -> List[Dict[str, Any]]:
        records = await self.history_repo.get_all_student_history(student_id)
        return records or []

    def _calculate_statistics(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        questions_asked = sum(
            record.get("questions_asked", 0) for record in records
        )

        weak_topics = [
            record.get("topic")
            for record in records
            if record.get("mastery_score", 1.0) < self.WEAK_MASTERY_THRESHOLD
        ]

        topic_statistics = {
            record.get("topic"): record.get("questions_asked", 0)
            for record in records
            if record.get("topic")
        }

        return {
            "questions_asked": questions_asked,
            "weak_topics": weak_topics,
            "topic_statistics": topic_statistics,
        }

    async def _generate_response(self, prompt: str) -> Dict[str, Any]:
        model_config = self.state_manager.get_model_config("AnalyticsAgent")
        model_config = dict(model_config)
        model_config["response_format"] = {"type": "json_object"}

        raw_response = await self.gateway.generate(prompt, **model_config)
        cleaned_response = self._clean_json_response(raw_response)

        return json.loads(cleaned_response)

    @staticmethod
    def _clean_json_response(raw_response: str) -> str:
        cleaned = raw_response.strip()

        if cleaned.startswith("```json"):
            cleaned = cleaned[len("```json"):]
        elif cleaned.startswith("```"):
            cleaned = cleaned[len("```"):]

        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

        return cleaned.strip()

    async def _store_report(
        self,
        session_id: str,
        response: AnalyticsResponse,
    ) -> None:
        summary = ""
        if response.student_analytics:
            summary = response.student_analytics.get("conceptual_gaps", "")

        await self.session_repo.log_session_report(
            session_id=session_id,
            subject=response.subject,
            grade=response.grade,
            questions_asked=response.questions_asked,
            average_difficulty=response.average_difficulty,
            weak_topics=response.weak_topics,
            topic_statistics=response.topic_statistics,
            summary=summary,
        )

    def _build_message(
        self,
        result: AgentResult,
        metadata: Dict[str, Any] | None = None,
    ) -> Msg:
        return Msg(
            name=self.name,
            content=result.model_dump_json(),
            metadata=metadata or {},
        )
