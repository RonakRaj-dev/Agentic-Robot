import time
import json
from typing import Any
import models.compat

from loguru import logger
from agentscope.agent import Agent
from agentscope.message import Msg

from models.llm_gateway import LLMGateway
from state.agentState import AgentStateManager
from state.sessionState import SessionStateManager
from models.schemas import AgentResult, get_content_str
from ai_teacher_robot.repositories.v3_repositories import LearningHistoryRepository
from .prompts import build_memory_prompt


class MemoryAgent(Agent):
    """
    MemoryAgent: Synthesizes chat logs and mastery records into Working, 
    Session, and Long-Term educational memory representations.
    """
    def __init__(self, name: str = "MemoryAgent", **kwargs: Any) -> None:
        super().__init__()
        self.name = name
        self.state_manager = AgentStateManager()
        self.session_manager = SessionStateManager()
        self.history_repo = LearningHistoryRepository()
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

        student_id = metadata.get("student_id") or metadata.get("username") or "default_student"
        
        try:
            chat_logs = self.session_manager.get_history(session_id)
            recent_turns = chat_logs[-6:]
            session_mem_str = "\n".join([f"{msg['sender']}: {msg['content']}" for msg in recent_turns])

            records = await self.history_repo.get_all_student_history(student_id)
            lt_mem_str = "\n".join([
                f"- Topic: '{r.get('topic')}' | Mastery: {r.get('mastery_score')} | Mistakes: {r.get('mistakes_logged', [])}"
                for r in records
            ]) if records else "No long term mastery recorded yet."

            prompt = build_memory_prompt(
                session_mem_str=session_mem_str,
                lt_mem_str=lt_mem_str,
            )

            model_config = self.state_manager.get_model_config("MemoryAgent")
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
            except Exception as parse_err:
                logger.warning(f"MemoryAgent JSON decode fallback: {parse_err}. Using default memory synthesis.")
                parsed_data = {
                    "working_memory": f"Student inquiry regarding curriculum concepts: {query[:100]}",
                    "session_context": "Active learning conversation turn.",
                    "long_term_memory": "Student profile active with standard mastery tracking."
                }

            execution_time = time.time() - start_time
            result = AgentResult(
                success=True,
                data=parsed_data,
                execution_time=execution_time
            )

            logger.info(f"MemoryAgent synthesized context successfully for student {student_id}")

            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Exception in MemoryAgent: {e}")
            result = AgentResult(
                success=False,
                data=None,
                error=f"Memory synthesis exception: {str(e)}",
                execution_time=execution_time
            )
            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )
