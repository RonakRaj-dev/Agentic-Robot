import time
import json
from typing import Any, Dict, List, Optional
from loguru import logger
from agentscope.message import UserMsg, AssistantMsg
from models.schemas import AgentResult, get_content_str


class GroupChatManager:
    """
    GroupChatManager: Implements Group Chat Orchestration (Multi-Agent Dialogue & Debate).
    Manages a round-table dialogue between TeachingAgent, AdaptiveLearningAgent, and 
    AssessmentAgent to refine lesson content, adjust grade vocabulary, and generate 
    consensus-backed educational explanations.
    """

    def __init__(
        self,
        teaching_agent: Any,
        adaptive_agent: Any,
        assessment_agent: Optional[Any] = None,
        max_rounds: int = 2,
    ) -> None:
        self.teaching_agent = teaching_agent
        self.adaptive_agent = adaptive_agent
        self.assessment_agent = assessment_agent
        self.max_rounds = max_rounds

    async def run_lesson_refinement_chat(
        self,
        query: str,
        context_str: str,
        adaptive_data: Dict[str, Any],
        pipeline_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Executes a round-table dialogue:
        Round 1: TeachingAgent creates initial lesson explanation.
        Round 2: AdaptiveLearningAgent critiques & refines for student grade level.
        Round 3 (Optional): TeachingAgent produces refined output + AssessmentAgent adds inline check question.
        """
        start_time = time.perf_counter()
        session_id = pipeline_metadata.get("session_id", "default_sess")
        grade = pipeline_metadata.get("grade", 5)
        
        logger.info(f"GroupChatManager: Starting round-table dialogue (Max rounds: {self.max_rounds}) for session {session_id}")
        
        # Round 1: TeachingAgent Draft
        prep_prompt = (
            f"ADAPTIVE TARGET PROFILE:\n"
            f"- Grade Level: Class {grade}\n"
            f"- Target Difficulty: {adaptive_data.get('difficulty_level', 'Intermediate')}\n"
            f"- Preferred Style: {adaptive_data.get('teaching_style', 'Conceptual')}\n\n"
            f"Reference Textbook Context:\n{context_str}\n\n"
            f"Question: {query}" if context_str else f"Question: {query}"
        )

        teach_msg = UserMsg(name="GroupChatHost", content=prep_prompt, metadata=pipeline_metadata)
        teach_reply = await self.teaching_agent.reply(teach_msg)
        
        teach_res = getattr(teach_reply, "metadata", {}).get("agent_result", {})
        initial_explanation = teach_res.get("data", {}).get("explanation", get_content_str(teach_reply))

        if self.max_rounds <= 1:
            return {
                "final_explanation": initial_explanation,
                "chat_rounds": 1,
                "dialogue_history": [{"speaker": "TeachingAgent", "content": initial_explanation}],
                "consensus_reached": True,
                "execution_time": time.perf_counter() - start_time,
            }

        # Round 2: AdaptiveLearningAgent Review & Critique
        review_prompt = (
            f"Please review this proposed lesson draft for a Class {grade} student:\n\n"
            f"PROPOSED EXPLANATION:\n{initial_explanation}\n\n"
            f"Evaluate if the vocabulary, tone, and pacing are appropriate for Class {grade} ({adaptive_data.get('difficulty_level', 'Intermediate')} level). "
            f"If changes are needed, provide brief refinement recommendations. If it is perfect, reply 'APPROVED'."
        )

        adap_msg = UserMsg(name="GroupChatHost", content=review_prompt, metadata=pipeline_metadata)
        adap_reply = await self.adaptive_agent.reply(adap_msg)
        critique_text = get_content_str(adap_reply)

        dialogue_history = [
            {"speaker": "TeachingAgent", "content": initial_explanation},
            {"speaker": "AdaptiveLearningAgent", "content": critique_text},
        ]

        if "APPROVED" in critique_text.upper():
            logger.info("GroupChatManager: AdaptiveLearningAgent APPROVED initial draft on Round 1!")
            return {
                "final_explanation": initial_explanation,
                "chat_rounds": 2,
                "dialogue_history": dialogue_history,
                "consensus_reached": True,
                "execution_time": time.perf_counter() - start_time,
            }

        # Round 3: TeachingAgent Refinement based on Adaptive Critique
        refinement_prompt = (
            f"Here is feedback from the Adaptive Learning Specialist:\n{critique_text}\n\n"
            f"Original Context:\n{context_str}\n\n"
            f"Original Question:\n{query}\n\n"
            f"Please rewrite and improve the lesson explanation incorporating the feedback."
        )

        refine_msg = UserMsg(name="GroupChatHost", content=refinement_prompt, metadata=pipeline_metadata)
        refine_reply = await self.teaching_agent.reply(refine_msg)
        refine_res = getattr(refine_reply, "metadata", {}).get("agent_result", {})
        final_explanation = refine_res.get("data", {}).get("explanation", get_content_str(refine_reply))

        dialogue_history.append({"speaker": "TeachingAgent (Refined)", "content": final_explanation})

        total_time = time.perf_counter() - start_time
        logger.info(f"GroupChatManager: Dialogue completed in {total_time:.3f}s across {len(dialogue_history)} turns")

        return {
            "final_explanation": final_explanation,
            "chat_rounds": len(dialogue_history),
            "dialogue_history": dialogue_history,
            "consensus_reached": True,
            "execution_time": total_time,
        }
