import time
import json
import re
from typing import Any
import models.compat
from loguru import logger
from agentscope.agent import Agent
from agentscope.message import Msg
from models.llm_gateway import LLMGateway
from state.agentState import AgentStateManager
from models.schemas import AgentResult, get_content_str

class RetrievalPlannerAgent(Agent):
    """
    RetrievalPlannerAgent: Analyzes student queries to decide if RAG context is required,
    and extracts search parameters (board, subject, class, chapter, strategy).
    """
    def __init__(self, name: str = "RetrievalPlannerAgent", **kwargs: Any) -> None:
        super().__init__()
        self.name = name
        self.state_manager = AgentStateManager()
        self.gateway = LLMGateway()

    async def reply(self, x: dict = None) -> dict:
        start_time = time.time()
        query = get_content_str(x)
        session_id = "default_sess"
        metadata_dict = {}
        if isinstance(x, dict):
            metadata_dict = x.get("metadata", {})
        elif hasattr(x, "metadata"):
            metadata_dict = getattr(x, "metadata", {}) or {}

        if not query.strip():
            execution_time = time.time() - start_time
            result = AgentResult(
                success=False,
                data=None,
                error="Input query to planner is empty.",
                execution_time=execution_time
            )
            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )

        try:
            # Load prompt config from 'prompts/retrievalplanner/config.json'
            # Fallback values if config not found on disk
            config = self.state_manager.load_agent_config("RetrievalPlannerAgent")
            
            grade_context = metadata_dict.get("grade")
            subject_context = metadata_dict.get("subject")
            class_str = str(grade_context) if grade_context is not None else "unknown"
            sub_str = str(subject_context) if subject_context else "unknown"

            system_prompt = self.state_manager.get_system_prompt(
                "RetrievalPlannerAgent", 
                query=query,
                class_context=class_str,
                subject_context=sub_str
            )
            model_config = self.state_manager.get_model_config("RetrievalPlannerAgent")

            # Create default system prompt if fallback config was generated
            if "RetrievalPlannerAgent" in system_prompt or len(system_prompt) < 100:
                system_prompt = f"""
Analyze the student's query and output a JSON decision object.
Context:
- User Class: {class_str}
- User Subject: {sub_str}

Rules:
- "rag_required": (boolean: true if query asks about curriculum, factual science, math, or specific book content. false for general greeting or conversational chit-chat).
- "subject": (string: "Mathematics", "Science", etc. or null if general. Default to "{sub_str}" unless query explicitly points elsewhere).
- "class": (string: class level "1" to "12" or null. Default to "{class_str}" unless query explicitly points elsewhere).
- "board": (string: e.g. "NCERT" or null).
- "chapter": (string: chapter number or null. ONLY non-null if a specific chapter is explicitly mentioned or strongly implied by the query. Otherwise null).
- "search_strategy": (string: "semantic", "bm25", or "hybrid").

Query: {query}
JSON:
"""

            response = await self.gateway.generate(system_prompt, **model_config)
            
            # Find and parse JSON block
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            plan_data = {}
            if json_match:
                plan_data = json.loads(json_match.group(0))
            else:
                # Basic heuristic fallback
                plan_data = {
                    "rag_required": True,
                    "subject": "Mathematics",
                    "class": "1",
                    "board": "NCERT",
                    "chapter": "1",
                    "search_strategy": "hybrid"
                }

            execution_time = time.time() - start_time
            result = AgentResult(
                success=True,
                data=plan_data,
                execution_time=execution_time
            )
            
            logger.info(f"RetrievalPlannerAgent plan: {plan_data}")
            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Exception in RetrievalPlannerAgent: {e}")
            result = AgentResult(
                success=False,
                data=None,
                error=f"Planner system exception: {str(e)}",
                execution_time=execution_time
            )
            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )
