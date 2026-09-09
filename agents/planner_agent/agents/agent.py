import time
import json
from typing import Any
import models.compat

from loguru import logger
from agentscope.agent import Agent
from agentscope.message import Msg

from models.llm_gateway import LLMGateway
from state.agentState import AgentStateManager
from models.schemas import AgentResult, PlannerResponse, get_content_str
from .prompts import build_planner_prompt


class PlannerAgent(Agent):
    """
    PlannerAgent: Dynamically formulates an autonomous teaching strategy 
    and chooses sub-agent execution pathways based on student messages.
    """
    def __init__(self, name: str = "PlannerAgent", **kwargs: Any) -> None:
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
        intent = metadata.get("intent") or ""

        try:
            prompt = build_planner_prompt(
                query=query,
                grade=grade,
                subject=subject,
                intent=intent,
            )

            model_config = self.state_manager.get_model_config("PlannerAgent")
            model_config = dict(model_config)
            model_config["response_format"] = {"type": "json_object"}

            raw_response = await self.gateway.generate(prompt, **model_config)
            
            import re
            cleaned = raw_response.strip()
            cleaned = re.sub(r'<think>.*?</think>', '', cleaned, flags=re.DOTALL).strip()
            if "```" in cleaned:
                cleaned = re.sub(r'```(?:json)?\s*', '', cleaned)
                cleaned = cleaned.replace("```", "").strip()
            json_match = re.search(r'\{.*\}', cleaned, flags=re.DOTALL)
            if json_match:
                cleaned = json_match.group(0)

            try:
                parsed_data = json.loads(cleaned)
                response_obj = PlannerResponse(**parsed_data)
            except Exception as e:
                logger.warning(f"PlannerAgent JSON parsing warning: {e}. Using fallback strategy.")
                response_obj = PlannerResponse(
                    teaching_strategy="direct_explanation",
                    execution_plan=["rag_agent", "teaching_agent"]
                )

            execution_time = time.time() - start_time
            result = AgentResult(
                success=True,
                data=response_obj.model_dump(),
                execution_time=execution_time
            )

            logger.info(f"PlannerAgent generated plan: strategy='{response_obj.teaching_strategy}' for query '{query}'")

            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Exception in PlannerAgent: {e}")
            result = AgentResult(
                success=False,
                data=None,
                error=f"Planning execution exception: {str(e)}",
                execution_time=execution_time
            )
            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )
