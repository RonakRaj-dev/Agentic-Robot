import time
import json
from typing import Any
import models.compat

from loguru import logger
from agentscope.agent import Agent
from agentscope.message import Msg

from .. import LLMGateway
from state.agentState import AgentStateManager
from models.schemas import AgentResult, TeachingResponse, get_content_str
from .prompts import RESPONSE_JSON_INSTRUCTION
from ai_teacher_robot.utils.text_cleaner import strain_text


class ResponseAgent(Agent):
    """
    Response Agent: Translates raw explanation payloads into the final
    structural delivery interface, validating schema parity against TeachingResponse.
    """
    def __init__(self, name: str = "ResponseAgent", **kwargs: Any) -> None:
        super().__init__()
        self.name = name
        self.state_manager = AgentStateManager()
        from .. import LLMGateway
        self.gateway = LLMGateway()

    async def reply(self, x: Any = None) -> Msg:
        start_time = time.time()
        
        raw_input = get_content_str(x)
        session_id = "default_sess"
        if isinstance(x, dict):
            session_id = x.get("metadata", {}).get("session_id", "default_sess")
        elif hasattr(x, "metadata"):
            session_id = getattr(x, "metadata", {}).get("session_id", "default_sess")

        if not raw_input.strip():
            execution_time = time.time() - start_time
            result = AgentResult(
                success=False,
                data=None,
                error="Input payload is empty or missing.",
                execution_time=execution_time
            )
            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )

        try:
            explanation_text = raw_input
            try:
                data_dict = json.loads(raw_input)
                if "data" in data_dict and data_dict["data"] and "explanation" in data_dict["data"]:
                    explanation_text = data_dict["data"]["explanation"]
            except Exception:
                pass
                
            config = self.state_manager.load_agent_config("ResponseAgent")
            prompt = self.state_manager.get_system_prompt("ResponseAgent", answer=explanation_text)
            model_config = dict(self.state_manager.get_model_config("ResponseAgent"))
            model_config["response_format"] = {"type": "json_object"}
            
            raw_response = await self.gateway.generate(
                prompt + RESPONSE_JSON_INSTRUCTION,
                **model_config
            )
            
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
            except Exception as parse_err:
                logger.warning(f"ResponseAgent JSON parse fallback: {parse_err}.")
                parsed_data = {}

            # Ensure teaching explanation is properly preserved or formatted
            if "answer" not in parsed_data or not parsed_data["answer"]:
                parsed_data["answer"] = strain_text(explanation_text)
            else:
                parsed_data["answer"] = strain_text(str(parsed_data["answer"]))
            
            if "summary" not in parsed_data or not parsed_data["summary"]:
                parsed_data["summary"] = "NCERT curriculum lesson explanation."
            else:
                parsed_data["summary"] = strain_text(str(parsed_data["summary"]))
                
            if "key_points" not in parsed_data or not isinstance(parsed_data["key_points"], list):
                parsed_data["key_points"] = []
            else:
                parsed_data["key_points"] = [strain_text(str(kp)) for kp in parsed_data["key_points"]]
                
            if "expression" not in parsed_data or not parsed_data["expression"]:
                parsed_data["expression"] = "EXPRESSION_NOD"
            if "teaching_mode" not in parsed_data:
                parsed_data["teaching_mode"] = "Conceptual"
            if "confidence_score" not in parsed_data:
                parsed_data["confidence_score"] = 0.90
                
            teaching_response = TeachingResponse(**parsed_data)
            
            execution_time = time.time() - start_time
            result = AgentResult(
                success=True,
                data=teaching_response.model_dump(),
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
                "Exception in ResponseAgent formatting: {}",
                str(e),
                agent=self.name,
                execution_time=round(execution_time, 3),
                session_id=session_id
            )
            result = AgentResult(
                success=False,
                data=None,
                error=f"Response structuring exception / schema mismatch: {str(e)}",
                execution_time=execution_time
            )
            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )
