import time
from typing import Any
import models.compat

from agentscope.agent import Agent
from agentscope.message import Msg
from loguru import logger

from models.llm_gateway import LLMGateway
from models.schemas import (
    AgentResult,
    get_content_str,
)
from state.agentState import AgentStateManager

from ai_teacher_robot.repositories.v3_repositories import (
    AssessmentHistoryRepository,
)

from .context import AssessmentContext
from .evaluator import AssessmentEvaluator
from .generator import AssessmentGenerator
from ..repositories.curriculum_repository import (
    CurriculumRepository,
)


class AssessmentAgent(Agent):

    def __init__(
        self,
        name: str = "AssessmentAgent",
        **kwargs: Any,
    ):
        super().__init__()
        self.name = name

        state_manager = AgentStateManager()
        from .. import LLMGateway
        gateway = LLMGateway()

        assessment_repo = AssessmentHistoryRepository()
        curriculum_repo = CurriculumRepository()

        self.generator = AssessmentGenerator(
            gateway=gateway,
            state_manager=state_manager,
            curriculum_repo=curriculum_repo,
        )

        self.evaluator = AssessmentEvaluator(
            gateway=gateway,
            state_manager=state_manager,
            assessment_repo=assessment_repo,
        )

    async def reply(self, x: Any = None) -> Msg:

        start = time.perf_counter()

        try:
            query = get_content_str(x)
            context = AssessmentContext.from_input(x)

            response = await self._process(
                query,
                context,
            )

            if context.action == "evaluate":
                await self.evaluator.persist(
                    session_id=context.session_id,
                    student_id=context.student_id,
                    topic=query,
                    questions=context.original_questions,
                    response=response,
                )

            return self._success(
                response,
                context,
                time.perf_counter() - start,
            )

        except Exception as exc:

            logger.exception(
                f"{self.name} failed: {exc}"
            )

            return self._failure(
                exc,
                time.perf_counter() - start,
            )

    async def _process(
        self,
        query: str,
        context: AssessmentContext,
    ):

        if context.action == "evaluate":

            return await self.evaluator.evaluate(
                topic=query,
                questions=context.original_questions,
                answers=context.student_answers,
            )

        return await self.generator.generate(
            topic=query,
            grade=context.grade,
            subject=context.subject,
        )

    def _success(
        self,
        response,
        context,
        execution_time,
    ):

        result = AgentResult(
            success=True,
            data=response.model_dump(),
            execution_time=execution_time,
        )

        logger.info(
            f"{self.name} completed | "
            f"action={context.action} | "
            f"time={execution_time:.3f}s"
        )

        return Msg(
            name=self.name,
            content=result.model_dump_json(),
            metadata={
                "agent_result": result.model_dump(),
                "action": context.action,
                "student_id": context.student_id,
                "session_id": context.session_id,
            },
        )

    def _failure(
        self,
        exc,
        execution_time,
    ):

        result = AgentResult(
            success=False,
            data=None,
            error=f"Assessment exception: {exc}",
            execution_time=execution_time,
        )

        return Msg(
            name=self.name,
            content=result.model_dump_json(),
            metadata={
                "agent_result": result.model_dump()
            },
        )