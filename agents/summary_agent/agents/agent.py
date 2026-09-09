import time
import json
from typing import Any
from loguru import logger
import models.compat
from agentscope.agent import Agent
from agentscope.message import Msg

from models.llm_gateway import LLMGateway
from state.agentState import AgentStateManager
from models.schemas import AgentResult, EndOfClassSummaryResponse, get_content_str
from .prompts import build_summary_prompt


class SummaryAgent(Agent):
    """
    SummaryAgent: Formulates dynamic, pedagogical end-of-class summaries
    with concepts, formulas, motivational quotes, and homework assignments.
    """
    def __init__(self, name: str = "SummaryAgent", **kwargs: Any) -> None:
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

        grade = metadata.get("grade") or 5
        subject = metadata.get("subject") or "General"

        try:
            prompt = build_summary_prompt(
                query=query,
                grade=grade,
                subject=subject,
            )

            model_config = self.state_manager.get_model_config("SummaryAgent")
            model_config = dict(model_config)
            model_config["response_format"] = {"type": "json_object"}

            raw_response = await self.gateway.generate(prompt, **model_config)
            
            cleaned = raw_response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            parsed_data = json.loads(cleaned)
            response_obj = EndOfClassSummaryResponse(**parsed_data)

            execution_time = time.time() - start_time
            result = AgentResult(
                success=True,
                data=response_obj.model_dump(),
                execution_time=execution_time
            )

            logger.info(f"SummaryAgent compiled session summary successfully for session {session_id}")

            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Exception in SummaryAgent: {e}")
            result = AgentResult(
                success=False,
                data=None,
                error=f"Summary creation exception: {str(e)}",
                execution_time=execution_time
            )
            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )
