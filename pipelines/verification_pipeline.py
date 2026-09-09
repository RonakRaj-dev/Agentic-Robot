import time
from typing import Dict, Any, Tuple
from loguru import logger
from agentscope.message import Msg

from agents.verification.fact_verification_agent import FactVerificationAgent

class VerificationPipeline:
    """Verification Pipeline executing factual consistency checking, contradiction checking, and citations generation."""
    def __init__(self) -> None:
        self.verifier = FactVerificationAgent(name="FactVerificationAgent")

    async def verify_response(
        self, 
        answer: str, 
        retrieved_chunks: list, 
        session_id: str = "default_sess"
    ) -> Tuple[str, Dict[str, Any]]:
        """Verifies teaching answer against retrieved chunks.
        
        Returns a tuple of (verified_answer, verification_metadata).
        """
        start_time = time.time()
        logger.info("Executing Verification Pipeline...")

        # Invoke Fact Verification Agent
        verify_msg = Msg(
            name="Supervisor", 
            content=answer, 
            metadata={
                "session_id": session_id,
                "retrieved_chunks": retrieved_chunks
            }
        )
        verify_reply = await self.verifier.reply(verify_msg)
        verify_res = getattr(verify_reply, "metadata", {}).get("agent_result", {})
        
        if not verify_res.get("success"):
            logger.warning(f"Fact Verification execution failed: {verify_res.get('error')}. Returning original answer.")
            return answer, {
                "status": "Verification Failed",
                "error": verify_res.get("error"),
                "confidence_percentage": 0,
                "warnings": "Verification system offline.",
                "citations": [],
                "execution_time": time.time() - start_time
            }

        verification_data = verify_res.get("data", {})
        verified_answer = verification_data.get("verified_answer", answer)
        duration = time.time() - start_time
        
        meta = {
            "status": verification_data.get("status", "Supported"),
            "reason": verification_data.get("reason", ""),
            "confidence_percentage": verification_data.get("confidence_percentage", 90),
            "warnings": verification_data.get("warnings"),
            "citations": verification_data.get("citations", []),
            "execution_time": duration
        }
        
        logger.info(f"Verification Pipeline finished in {duration:.2f} seconds. Status: {meta['status']}")
        return verified_answer, meta
