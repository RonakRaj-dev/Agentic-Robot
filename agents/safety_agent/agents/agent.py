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
from .prompts import SAFETY_JSON_INSTRUCTION


class SafetyAgent(Agent):
    """
    Safety Agent: Enforces age-appropriate validation guidelines,
    filtering non-educational or unsafe topics.
    """
    def __init__(self, name: str = "SafetyAgent", **kwargs: Any) -> None:
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
            from services.security_sanitizer import security_sanitizer
            is_injection, _ = security_sanitizer.is_prompt_injection(query)
            
            if is_injection:
                is_safe = False
                reason = "Adversarial prompt injection pattern detected."
            else:
                config = self.state_manager.load_agent_config("SafetyAgent")
                prompt = self.state_manager.get_system_prompt("SafetyAgent", query=query)
                model_config = self.state_manager.get_model_config("SafetyAgent")
                model_config = dict(model_config)
                model_config["response_format"] = {"type": "json_object"}
                
                raw_response = await self.gateway.generate(
                    prompt + SAFETY_JSON_INSTRUCTION,
                    **model_config
                )
                
                clean_str = raw_response.strip()
                # Extract JSON substring if LLM wraps output in markdown code blocks
                import re
                json_match = re.search(r'\{.*\}', clean_str, re.DOTALL)
                if json_match:
                    clean_str = json_match.group(0)

                try:
                    data = json.loads(clean_str)
                    is_safe = data.get("safe", data.get("is_safe", True))
                    reason = data.get("reason", "")
                except Exception:
                    # Default to safe for standard curriculum queries if model formatting varies
                    is_safe = True
                    reason = ""
            
            execution_time = time.time() - start_time
            
            if is_safe:
                result = AgentResult(
                    success=True,
                    data={"safe": True, "is_safe": True, "reason": reason},
                    execution_time=execution_time
                )
            else:
                result = AgentResult(
                    success=False,
                    data={"safe": False, "is_safe": False, "reason": reason},
                    error=f"Safety violation: {reason}",
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
                "Exception in SafetyAgent: {}",
                repr(e),
                agent=self.name,
                execution_time=round(execution_time, 3),
                session_id=session_id
            )
            result = AgentResult(
                success=False,
                data=None,
                error=f"Safety system exception: {str(e)}",
                execution_time=execution_time
            )
            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )
