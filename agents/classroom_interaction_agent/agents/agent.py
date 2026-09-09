import time
import json
from typing import Any
import models.compat

from loguru import logger
from agentscope.agent import Agent
from agentscope.message import Msg

from models.llm_gateway import LLMGateway
from state.agentState import AgentStateManager
from models.schemas import AgentResult, InteractiveClassroomResponse, get_content_str
from .prompts import build_interaction_prompt


class ClassroomInteractionAgent(Agent):
    """
    ClassroomInteractionAgent: Manages educational games (Quiz Mode, Rapid Fire,
    Vocabulary Game, Science Quiz) with timers, hints, and score mechanics.
    """
    def __init__(self, name: str = "ClassroomInteractionAgent", **kwargs: Any) -> None:
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

        game_mode = metadata.get("game_mode", "Quiz Mode")
        current_score = metadata.get("score", 0)
        hints_used = metadata.get("hints_used", [])
        student_id = metadata.get("student_id") or metadata.get("username") or "student"

        try:
            prompt = build_interaction_prompt(
                game_mode=game_mode,
                current_score=current_score,
                query=query,
                student_id=student_id,
            )

            model_config = self.state_manager.get_model_config("ClassroomInteractionAgent")
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
            response_obj = InteractiveClassroomResponse(**parsed_data)

            execution_time = time.time() - start_time
            result = AgentResult(
                success=True,
                data=response_obj.model_dump(),
                execution_time=execution_time
            )

            logger.info(f"ClassroomInteractionAgent processed turn in game mode {game_mode}")

            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Exception in ClassroomInteractionAgent: {e}")
            result = AgentResult(
                success=False,
                data=None,
                error=f"Game interaction exception: {str(e)}",
                execution_time=execution_time
            )
            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )
