import time
import json
from typing import Any, Dict, List, Tuple
from loguru import logger
from agentscope.message import UserMsg, AssistantMsg
from models.schemas import AgentResult, get_content_str


class MagneticAttractorEngine:
    """
    MagneticAttractorEngine: Implements Magnetic Attractor Orchestration.
    Drives iterative state convergence where agent outputs are evaluated against 
    target constraint attractors (Factual Groundedness Target F >= 0.85). If the state 
    drifts away from the attractor, a magnetic constraint pull prompt forces re-generation 
    until convergence is reached.
    """

    def __init__(
        self,
        teaching_agent: Any,
        verification_agent: Any,
        target_groundedness: float = 0.85,
        max_attractor_attempts: int = 2,
    ) -> None:
        self.teaching_agent = teaching_agent
        self.verification_agent = verification_agent
        self.target_groundedness = target_groundedness
        self.max_attempts = max_attractor_attempts

    async def converge_explanation_attractor(
        self,
        initial_explanation: str,
        retrieved_chunks: List[Dict[str, Any]],
        grounded_query: str,
        pipeline_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Runs the attractor loop:
        1. Evaluates factual similarity & contradictions via FactVerificationAgent.
        2. If groundedness < target_groundedness and attempts remain:
           Constructs a magnetic constraint pull feedback prompt and re-invokes TeachingAgent.
        3. Converges when target threshold is reached or max iterations hit.
        """
        start_time = time.perf_counter()
        session_id = pipeline_metadata.get("session_id", "default_sess")
        
        current_explanation = initial_explanation
        attempts = 0
        converged = False
        verification_data: Dict[str, Any] = {}

        logger.info(f"MagneticAttractorEngine: Starting convergence loop for session {session_id} (Target F={self.target_groundedness})")

        while attempts < self.max_attempts and not converged:
            attempts += 1
            
            # Step 1: Evaluate distance to factual attractor
            verify_msg = UserMsg(
                name="AttractorEngine",
                content=current_explanation,
                metadata={"session_id": session_id, "retrieved_chunks": retrieved_chunks},
            )
            verify_reply = await self.verification_agent.reply(verify_msg)
            v_res_dict = getattr(verify_reply, "metadata", {}).get("agent_result", {})
            verification_data = v_res_dict.get("data", {}) if v_res_dict.get("success", False) else {}

            confidence_pct = verification_data.get("confidence_percentage", 100)
            groundedness_score = confidence_pct / 100.0
            unsupported_claims = verification_data.get("unsupported_claims", [])

            logger.info(
                f"MagneticAttractorEngine [Attempt {attempts}/{self.max_attempts}]: "
                f"Groundedness={groundedness_score:.2f} (Target={self.target_groundedness})"
            )

            # Check if converged onto attractor state
            if groundedness_score >= self.target_groundedness or not unsupported_claims:
                converged = True
                logger.info(f"MagneticAttractorEngine: State CONVERGED to factual attractor in {attempts} attempt(s)!")
                break

            # If not converged and attempts remain, calculate Magnetic Pull Feedback Prompt
            if attempts < self.max_attempts:
                unsupported_str = "\n".join([f"- {c}" for c in unsupported_claims])
                magnetic_pull_prompt = (
                    f"FACTUAL GROUNDEDNESS ATTRACTOR WARNING:\n"
                    f"Your previous explanation contained statements unsupported by the textbook RAG sources:\n"
                    f"{unsupported_str}\n\n"
                    f"MAGNETIC CONSTRAINT FORCE:\n"
                    f"Please rewrite the explanation. STAGE ONLY claims directly supported by the Reference Context below. "
                    f"Eliminate hallucinated facts.\n\n"
                    f"{grounded_query}"
                )

                logger.info("MagneticAttractorEngine: Applying magnetic constraint pull force for re-generation...")
                teach_msg = UserMsg(name="AttractorEngine", content=magnetic_pull_prompt, metadata=pipeline_metadata)
                teach_reply = await self.teaching_agent.reply(teach_msg)
                teach_res = getattr(teach_reply, "metadata", {}).get("agent_result", {})
                
                if teach_res.get("success", False):
                    current_explanation = teach_res.get("data", {}).get("explanation", current_explanation)

        # Use the highest quality generated explanation
        final_answer = current_explanation
        total_time = time.perf_counter() - start_time

        return {
            "final_explanation": final_answer,
            "attractor_attempts": attempts,
            "converged": converged,
            "verification_data": verification_data,
            "execution_time": total_time,
        }
