import time
import json
from typing import Any
import models.compat

from loguru import logger
from agentscope.agent import Agent
from agentscope.message import Msg
from .. import LLMGateway
from state.agentState import AgentStateManager
from models.schemas import AgentResult, get_content_str
from .prompts import VALIDATION_JSON_INSTRUCTION


class ValidationAgent(Agent):
    """
    Validation Agent: Sanitizes inbound queries, detects injection vectors,
    duplicates, empty text, or token overflows.
    """
    def __init__(self, name: str = "ValidationAgent", **kwargs: Any) -> None:
        super().__init__()
        self.name = name
        self.state_manager = AgentStateManager()
        from .. import LLMGateway
        self.gateway = LLMGateway()

    async def reply(self, x: Any = None) -> Msg:
        start_time = time.time()
        
        query = get_content_str(x)
        session_id = "default_sess"
        if isinstance(x, dict):
            session_id = (x.get("metadata") or {}).get("session_id", "default_sess")
        elif hasattr(x, "metadata"):
            session_id = (getattr(x, "metadata", None) or {}).get("session_id", "default_sess")

        cleaned_query = query.strip()
        if not cleaned_query:
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

        if len(cleaned_query) < 3:
            execution_time = time.time() - start_time
            result = AgentResult(
                success=False,
                data={"valid": False},
                error="Sanitization violation: query must be at least 3 characters.",
                execution_time=execution_time
            )
            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )
        
        try:
            config = self.state_manager.load_agent_config("ValidationAgent")
            prompt = self.state_manager.get_system_prompt("ValidationAgent", query=query)
            model_config = self.state_manager.get_model_config("ValidationAgent")
            model_config = dict(model_config)
            model_config["response_format"] = {"type": "json_object"}
            
            raw_response = await self.gateway.generate(
                prompt + VALIDATION_JSON_INSTRUCTION,
                **model_config
            )
            
            clean_str = raw_response.strip()
            import re
            json_match = re.search(r'\{.*\}', clean_str, re.DOTALL)
            if json_match:
                clean_str = json_match.group(0)

            try:
                data = json.loads(clean_str)
                is_valid = data.get("valid", True)
                reason = data.get("reason", "")
            except Exception:
                is_valid = True
                reason = ""
            
            execution_time = time.time() - start_time
            
            if is_valid:
                result = AgentResult(
                    success=True,
                    data={"valid": True},
                    execution_time=execution_time
                )
            else:
                result = AgentResult(
                    success=False,
                    data={"valid": False},
                    error=f"Sanitization violation: {reason}",
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
                "Exception in ValidationAgent: {}",
                repr(e),
                agent=self.name,
                execution_time=round(execution_time, 3),
                session_id=session_id
            )
            result = AgentResult(
                success=False,
                data=None,
                error=f"Validation system exception: {str(e)}",
                execution_time=execution_time
            )
            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )
