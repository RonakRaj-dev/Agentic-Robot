import time
from typing import Dict, Any, Tuple
from loguru import logger
from agentscope.message import Msg

from agents.retrieval.retrieval_planner_agent import RetrievalPlannerAgent
from agents.retrieval.curriculum_rag_agent import CurriculumRAGAgent
from agents.retrieval.context_builder import ContextBuilder
from agents.teaching_agent import TeachingAgent

class GroundingPipeline:
    """Grounding Pipeline coordinating retrieval planning, context assembly, and the Teaching explanation generation."""
    def __init__(self) -> None:
        self.planner = RetrievalPlannerAgent(name="RetrievalPlannerAgent")
        self.rag_agent = CurriculumRAGAgent(name="CurriculumRAGAgent")
        self.context_builder = ContextBuilder()
        self.teaching_agent = TeachingAgent(name="TeachingAgent")

    async def execute_teaching(self, query: str, session_id: str = "default_sess") -> Tuple[str, Dict[str, Any]]:
        """Executes the grounding loop: Planning -> Retrieval (optional) -> Context building -> Teaching answer generation.
        
        Returns a tuple of (teaching_answer, execution_metadata).
        """
        start_time = time.time()
        logger.info(f"Executing Grounding Pipeline for query: '{query}'")

        # 1. Retrieval Planner
        planner_msg = Msg(name="Supervisor", content=query, metadata={"session_id": session_id})
        planner_reply = await self.planner.reply(planner_msg)
        planner_res = getattr(planner_reply, "metadata", {}).get("agent_result", {})
        
        planner_data = planner_res.get("data", {}) if planner_res.get("success") else {}
        rag_required = planner_data.get("rag_required", True)
        
        retrieved_chunks = []
        context_str = ""

        # 2. Curriculum RAG (if planned)
        if rag_required:
            logger.info("Planner decided RAG is REQUIRED.")
            rag_msg = Msg(
                name="Supervisor", 
                content=query, 
                metadata={
                    "session_id": session_id,
                    "planner_result": planner_data
                }
            )
            rag_reply = await self.rag_agent.reply(rag_msg)
            rag_res = getattr(rag_reply, "metadata", {}).get("agent_result", {})
            
            if rag_res.get("success"):
                retrieved_chunks = rag_res.get("data", {}).get("chunks", [])
                # Build context
                context_str = self.context_builder.build_context(retrieved_chunks)
            else:
                logger.warning(f"RAG Retrieval failed: {rag_res.get('error')}")
        else:
            logger.info("Planner decided RAG is NOT required.")

        # 3. Grounding: Embed context into the teaching agent explanation prompt
        grounded_query = query
        if context_str:
            grounded_query = f"""
Use the following official curriculum source texts to formulate your response. Make sure to cite these details where appropriate.

Curriculum Reference Context:
{context_str}

---
Student educational question to explain: {query}
"""

        # 4. Invoke Teaching Agent
        logger.info("Invoking TeachingAgent with grounded query...")
        teach_msg = Msg(name="Supervisor", content=grounded_query, metadata={"session_id": session_id})
        teach_reply = await self.teaching_agent.reply(teach_msg)
        teach_res = getattr(teach_reply, "metadata", {}).get("agent_result", {})
        
        teaching_answer = ""
        if teach_res.get("success"):
            teaching_answer = teach_res.get("data", {}).get("explanation", "")
        else:
            raise RuntimeError(f"TeachingAgent failed: {teach_res.get('error')}")

        duration = time.time() - start_time
        meta = {
            "planner_data": planner_data,
            "rag_required": rag_required,
            "retrieved_chunks": retrieved_chunks,
            "context_str": context_str,
            "execution_time": duration
        }
        
        logger.info(f"Grounding Pipeline finished in {duration:.2f} seconds.")
        return teaching_answer, meta
