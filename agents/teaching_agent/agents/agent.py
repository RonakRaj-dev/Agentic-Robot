import time
import re
from typing import Any
import models.compat

from loguru import logger
from agentscope.agent import Agent
from agentscope.message import Msg
from .. import LLMGateway
from state.agentState import AgentStateManager
from models.schemas import AgentResult, get_content_str
from .prompts import get_persona_instruction, get_class_subject_agent_prompt


class TeachingAgent(Agent):
    """
    Teaching Agent: Crafts simple instructional explanations and breakdowns.
    """
    def __init__(self, name: str = "TeachingAgent", **kwargs: Any) -> None:
        super().__init__()
        self.name = name
        self.state_manager = AgentStateManager()
        from .. import LLMGateway
        self.gateway = LLMGateway()

    async def reply(self, x: Any = None) -> Msg:
        start_time = time.time()
        
        query = get_content_str(x)
        session_id = "default_sess"
        metadata = {}
        if isinstance(x, dict):
            metadata = x.get("metadata", {})
            session_id = metadata.get("session_id", "default_sess")
        elif hasattr(x, "metadata"):
            metadata = getattr(x, "metadata", {}) or {}
            session_id = metadata.get("session_id", "default_sess")

        if not query.strip():
            execution_time = time.time() - start_time
            result = AgentResult(
                success=False,
                data=None,
                error="Input query is empty or missing.",
                execution_time=execution_time
            )
            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )

        try:
            grade_val = metadata.get("grade") or metadata.get("planner_result", {}).get("class")
            grade = None
            if grade_val is not None:
                try:
                    match = re.search(r'\d+', str(grade_val))
                    if match:
                        grade = int(match.group(0))
                except Exception:
                    pass

            subject = metadata.get("subject") or "Science"
            if "Social" in str(subject) or "History" in str(subject) or "Geo" in str(subject) or "Civ" in str(subject):
                subject = "Social Science"

            config = self.state_manager.load_agent_config("TeachingAgent")
            model_config = dict(self.state_manager.get_model_config("TeachingAgent"))
            
            system_prompt = get_class_subject_agent_prompt(grade, subject, "TeachingAgent")
            prompt = f"{system_prompt}\n\nStudent Query / Curriculum Context:\n{query}"

            explanation = await self.gateway.generate(prompt, **model_config)
            
            execution_time = time.time() - start_time
            result = AgentResult(
                success=True,
                data={"explanation": explanation},
                execution_time=execution_time
            )
            
            logger.info(
                "Agent completed execution",
                agent=self.name,
                execution_time=round(execution_time, 3),
                session_id=session_id
            )
            
            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                "Exception in TeachingAgent: {}",
                str(e),
                agent=self.name,
                execution_time=round(execution_time, 3),
                session_id=session_id
            )
            result = AgentResult(
                success=False,
                data=None,
                error=f"Teaching system exception: {str(e)}",
                execution_time=execution_time
            )
            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )
