import time
import json
from typing import Any, Dict, Optional
from loguru import logger

import models.compat
from agentscope.agents import Agent
from agentscope.message import UserMsg, AssistantMsg

from models.schemas import AgentResult, TeachingResponse, get_content_str
from state.sessionState import SessionStateManager
from state.agentState import AgentStateManager

from agents.validator_agent import ValidationAgent
from agents.safety_agent import SafetyAgent
from agents.teaching_agent import TeachingAgent
from agents.response_agent import ResponseAgent


class ClassroomSupervisorAgent(Agent):
    """
    ClassroomSupervisorAgent: Core orchestrator. Directs conversational routing pipelines,
    handles safety/validation boundaries, runs explanations, structures response schema parity,
    tracks session state, and implements locking/retry policies.
    """
    def __init__(self, name: str = "ClassroomSupervisorAgent", **kwargs: Any) -> None:
        super().__init__()
        self.name = name
        self.session_manager = SessionStateManager()
        self.agent_state_manager = AgentStateManager()
        
        self.validation_agent = ValidationAgent(name="ValidationAgent")
        self.safety_agent = SafetyAgent(name="SafetyAgent")
        self.teaching_agent = TeachingAgent(name="TeachingAgent")
        self.response_agent = ResponseAgent(name="ResponseAgent")

    async def reply(self, x: Any = None) -> AssistantMsg:
        start_time = time.time()
        
        query = get_content_str(x)
        session_id = "default_sess"
        if isinstance(x, dict):
            session_id = x.get("metadata", {}).get("session_id", "default_sess")
        elif hasattr(x, "metadata"):
            session_id = getattr(x, "metadata", {}).get("session_id", "default_sess")

        if not query.strip():
            execution_time = time.time() - start_time
            result = AgentResult(
                success=False,
                data=None,
                error="Input query to supervisor is empty.",
                execution_time=execution_time
            )
            return AssistantMsg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )

        lock_name = f"session:{session_id}"
        if not self.session_manager.acquire_lock(lock_name, expire_seconds=15):
            execution_time = time.time() - start_time
            logger.warning(f"Lock active for session {session_id}. Rejecting concurrent query.")
            result = AgentResult(
                success=False,
                data=None,
                error="Concurrent message error: session is locked processing another request.",
                execution_time=execution_time
            )
            return AssistantMsg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )

        try:
            self.session_manager.save_message(session_id, sender="User", content=query)
            
            pipeline_metadata = {
                "session_id": session_id
            }
            
            # --- STEP 1: VALIDATION ---
            step_start = time.time()
            val_msg = UserMsg(name="Supervisor", content=query, metadata=pipeline_metadata)
            val_reply = await self.validation_agent.reply(val_msg)
            
            val_metadata = getattr(val_reply, "metadata", {}) or {}
            val_res_dict = val_metadata.get("agent_result", {})
            val_time = time.time() - step_start
            
            val_success = val_res_dict.get("success", False)
            self.session_manager.save_execution_state(
                session_id=session_id,
                agent="ValidationAgent",
                status="success" if val_success else "failed",
                execution_time=val_time,
                error=val_res_dict.get("error")
            )
            
            if not val_success:
                execution_time = time.time() - start_time
                result = AgentResult(
                    success=False,
                    data=None,
                    error=val_res_dict.get("error", "Sanitization failed."),
                    execution_time=execution_time
                )
                logger.warning(f"Session {session_id} failed validation check.")
                return AssistantMsg(
                    name=self.name,
                    content=result.model_dump_json(),
                    metadata={"agent_result": result.model_dump()}
                )

            # --- STEP 2: SAFETY ---
            step_start = time.time()
            safety_msg = UserMsg(name="Supervisor", content=query, metadata=pipeline_metadata)
            safety_reply = await self.safety_agent.reply(safety_msg)
            
            safety_metadata = getattr(safety_reply, "metadata", {}) or {}
            safety_res_dict = safety_metadata.get("agent_result", {})
            safety_time = time.time() - step_start
            
            safety_success = safety_res_dict.get("success", False)
            self.session_manager.save_execution_state(
                session_id=session_id,
                agent="SafetyAgent",
                status="success" if safety_success else "failed",
                execution_time=safety_time,
                error=safety_res_dict.get("error")
            )
            
            if not safety_success:
                execution_time = time.time() - start_time
                result = AgentResult(
                    success=False,
                    data=None,
                    error=safety_res_dict.get("error", "Safety check failed."),
                    execution_time=execution_time
                )
                logger.warning(f"Session {session_id} failed safety check.")
                return AssistantMsg(
                    name=self.name,
                    content=result.model_dump_json(),
                    metadata={"agent_result": result.model_dump()}
                )

            # --- STEP 3: TEACHING (With retries if needed) ---
            teaching_res_dict = {}
            teaching_success = False
            max_agent_retries = 2
            teach_reply = None
            
            for attempt in range(max_agent_retries):
                step_start = time.time()
                teach_msg = UserMsg(name="Supervisor", content=query, metadata=pipeline_metadata)
                teach_reply = await self.teaching_agent.reply(teach_msg)
                
                teach_metadata = getattr(teach_reply, "metadata", {}) or {}
                teaching_res_dict = teach_metadata.get("agent_result", {})
                teaching_time = time.time() - step_start
                
                teaching_success = teaching_res_dict.get("success", False)
                self.session_manager.save_execution_state(
                    session_id=session_id,
                    agent="TeachingAgent",
                    status="success" if teaching_success else f"failed-attempt-{attempt+1}",
                    execution_time=teaching_time,
                    error=teaching_res_dict.get("error")
                )
                
                if teaching_success:
                    break
                logger.warning(f"TeachingAgent failed on attempt {attempt+1}. Retrying...")
                time.sleep(0.5)

            if not teaching_success or teach_reply is None:
                execution_time = time.time() - start_time
                result = AgentResult(
                    success=False,
                    data=None,
                    error=teaching_res_dict.get("error", "Teaching agent failed execution."),
                    execution_time=execution_time
                )
                logger.error(f"Session {session_id} failed teaching step after retries.")
                return AssistantMsg(
                    name=self.name,
                    content=result.model_dump_json(),
                    metadata={"agent_result": result.model_dump()}
                )

            # --- STEP 4: RESPONSE STRUCTURING & PARITY ---
            step_start = time.time()
            response_msg = UserMsg(name="Supervisor", content=get_content_str(teach_reply), metadata=pipeline_metadata)
            response_reply = await self.response_agent.reply(response_msg)
            
            response_metadata = getattr(response_reply, "metadata", {}) or {}
            response_res_dict = response_metadata.get("agent_result", {})
            response_time = time.time() - step_start
            
            response_success = response_res_dict.get("success", False)
            self.session_manager.save_execution_state(
                session_id=session_id,
                agent="ResponseAgent",
                status="success" if response_success else "failed",
                execution_time=response_time,
                error=response_res_dict.get("error")
            )
            
            if not response_success:
                execution_time = time.time() - start_time
                result = AgentResult(
                    success=False,
                    data=None,
                    error=response_res_dict.get("error", "Response structuring failed."),
                    execution_time=execution_time
                )
                logger.error(f"Session {session_id} failed response structure formatting.")
                return AssistantMsg(
                    name=self.name,
                    content=result.model_dump_json(),
                    metadata={"agent_result": result.model_dump()}
                )

            # --- PIPELINE SUCCESS ---
            execution_time = time.time() - start_time
            final_data = response_res_dict.get("data", {})
            
            self.session_manager.save_message(
                session_id=session_id,
                sender="Supervisor",
                content=final_data.get("answer", "")
            )
            
            result = AgentResult(
                success=True,
                data=final_data,
                execution_time=execution_time
            )
            
            logger.info(
                "Agent completed execution",
                agent=self.name,
                execution_time=round(execution_time, 3),
                session_id=session_id
            )
            
            return AssistantMsg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Exception inside ClassroomSupervisorAgent pipeline: {e}",
                agent=self.name,
                execution_time=round(execution_time, 3),
                session_id=session_id
            )
            result = AgentResult(
                success=False,
                data=None,
                error=f"Supervisor pipeline system exception: {str(e)}",
                execution_time=execution_time
            )
            return AssistantMsg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )
        finally:
            self.session_manager.release_lock(lock_name)
