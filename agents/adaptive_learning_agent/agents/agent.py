import json
import time
from typing import Any, Dict
import models.compat

from loguru import logger
from agentscope.agent import Agent
from agentscope.message import Msg

from ai_teacher_robot.repositories.v3_repositories import LearningHistoryRepository
from .. import LLMGateway
from models.schemas import AdaptiveLearningResponse, AgentResult, get_content_str
from state.agentState import AgentStateManager
from .prompts import ADAPTIVE_LEARNING_PROMPT_TEMPLATE


class AdaptiveLearningAgent(Agent):
    """
    AdaptiveLearningAgent analyzes a student's current query and
    historical learning performance to determine:

    - Appropriate difficulty level
    - Preferred teaching style
    - Recommended learning path
    """

    DEFAULT_SESSION_ID = "default_sess"
    DEFAULT_STUDENT_ID = "default_student"
    DEFAULT_GRADE = 5
    DEFAULT_SUBJECT = "General"

    def __init__(
        self,
        name: str = "AdaptiveLearningAgent",
        **kwargs: Any,
    ) -> None:
        super().__init__()
        self.name = name

        self.state_manager = AgentStateManager()
        from .. import LLMGateway
        self.gateway = LLMGateway()
        self.history_repo = LearningHistoryRepository()

    async def reply(self, x: Any = None) -> Msg:
        start_time = time.perf_counter()

        try:
            query = get_content_str(x)
            metadata = self._extract_metadata(x)

            student_id = self._get_student_id(metadata)
            session_id = metadata.get(
                "session_id",
                self.DEFAULT_SESSION_ID,
            )
            grade = metadata.get("grade", self.DEFAULT_GRADE)
            subject = metadata.get(
                "subject",
                self.DEFAULT_SUBJECT,
            )

            logger.info(
                f"{self.name} processing request | "
                f"student_id={student_id} | "
                f"session_id={session_id}"
            )

            history = await self._get_learning_history(student_id)

            prompt = self._build_prompt(
                query=query,
                history=history,
                grade=grade,
                subject=subject,
            )

            parsed_response = await self._generate_response(prompt)
            response = AdaptiveLearningResponse(**parsed_response)

            execution_time = time.perf_counter() - start_time

            result = AgentResult(
                success=True,
                data=response.model_dump(),
                execution_time=execution_time,
            )

            logger.info(
                f"{self.name} completed successfully | "
                f"student_id={student_id} | "
                f"difficulty={response.difficulty_level} | "
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
                error=f"Adaptive learning exception: {exc}",
                execution_time=execution_time,
            )

            return self._build_message(
                result=result,
                metadata={
                    "agent_result": result.model_dump(),
                },
            )

    def _extract_metadata(self, x: Any) -> Dict[str, Any]:
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

    async def _get_learning_history(
        self,
        student_id: str,
    ) -> str:
        records = await self.history_repo.get_all_student_history(
            student_id
        )

        if not records:
            return "No historical records found for this student."

        history_lines = []
        for record in records:
            topic = record.get("topic", "Unknown")
            mastery = record.get("mastery_score", "Unknown")
            mistakes = record.get("mistakes_logged", [])

            history_lines.append(
                f"Topic: {topic}, "
                f"Mastery: {mastery}, "
                f"Mistakes: {mistakes}"
            )

        return "\n".join(history_lines)

    def _build_prompt(
        self,
        query: str,
        history: str,
        grade: Any,
        subject: str,
    ) -> str:
        system_prompt = self.state_manager.get_system_prompt(
            "AdaptiveLearningAgent",
            query=query,
        )

        return ADAPTIVE_LEARNING_PROMPT_TEMPLATE.format(
            system_prompt=system_prompt,
            history=history,
            grade=grade,
            subject=subject,
            query=query,
        )

    async def _generate_response(
        self,
        prompt: str,
    ) -> Dict[str, Any]:
        model_config = self.state_manager.get_model_config(
            "AdaptiveLearningAgent"
        )

        model_config = dict(model_config)
        model_config["response_format"] = {
            "type": "json_object",
        }

        raw_response = await self.gateway.generate(
            prompt,
            **model_config,
        )

        try:
            cleaned_response = self._clean_json_response(raw_response)
            if cleaned_response:
                return json.loads(cleaned_response)
        except Exception as e:
            logger.warning(f"AdaptiveLearningAgent JSON decode warning: {e}. Using fallback.")
        return {
            "difficulty_level": "Intermediate",
            "pedagogical_strategy": "Conceptual Explanation",
            "adaptations": ["Provide clear explanation"],
            "scaffolding_needed": False
        }

    @staticmethod
    def _clean_json_response(raw_response: str) -> str:
        import re
        cleaned = raw_response.strip()
        cleaned = re.sub(r'<think>.*?</think>', '', cleaned, flags=re.DOTALL).strip()
        if "```" in cleaned:
            cleaned = re.sub(r'```(?:json)?\s*', '', cleaned)
            cleaned = cleaned.replace("```", "").strip()
        json_match = re.search(r'\{.*\}', cleaned, flags=re.DOTALL)
        if json_match:
            return json_match.group(0)
        return cleaned.strip()

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
