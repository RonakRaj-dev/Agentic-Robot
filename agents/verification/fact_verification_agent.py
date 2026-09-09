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
from agents.verification.contradiction_checker import ContradictionChecker
from agents.verification.citation_generator import CitationGenerator

class FactVerificationAgent(Agent):
    """
    FactVerificationAgent: Compares TeachingAgent's output against retrieved chunks,
    marks support status, identifies unsupported claims, and generates citations.
    """
    def __init__(self, name: str = "FactVerificationAgent", **kwargs: Any) -> None:
        super().__init__()
        self.name = name
        self.state_manager = AgentStateManager()
        self.gateway = LLMGateway()
        self.contradiction_checker = ContradictionChecker()
        self.citation_generator = CitationGenerator()
        from ai_teacher_robot.rag.embedding.embedding_generator import EmbeddingGenerator
        self.embedding_generator = EmbeddingGenerator()

    async def reply(self, x: dict = None) -> dict:
        start_time = time.time()
        
        metadata = {}
        if isinstance(x, dict):
            metadata = x.get("metadata", {})
        elif hasattr(x, "metadata"):
            metadata = getattr(x, "metadata", {}) or {}

        session_id = metadata.get("session_id", "default_sess")
        teaching_answer = get_content_str(x)
        retrieved_chunks = metadata.get("retrieved_chunks", [])
        
        if not teaching_answer.strip():
            execution_time = time.time() - start_time
            result = AgentResult(
                success=False,
                data=None,
                error="Teaching answer to verify is empty.",
                execution_time=execution_time
            )
            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )

        try:
            import numpy as np
            
            # 1. Programmatically split the teaching explanation into sentences
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', teaching_answer) if s.strip()]
            
            # Embed sentences in a batch
            sentence_embeddings = []
            if sentences:
                sentence_embeddings = self.embedding_generator.generate_embeddings(sentences)
            
            # Extract and embed all retrieved chunk texts
            chunk_texts = [c.get("chunk_text") or c.get("text") or "" for c in retrieved_chunks]
            chunk_texts = [t for t in chunk_texts if t.strip()]
            chunk_embeddings = []
            if chunk_texts:
                chunk_embeddings = self.embedding_generator.generate_embeddings(chunk_texts)
            
            unsupported_claims = []
            
            # Cosine similarity helper
            def get_cosine_similarity(v1, v2):
                a = np.array(v1)
                b = np.array(v2)
                norm_a = np.linalg.norm(a)
                norm_b = np.linalg.norm(b)
                if norm_a == 0 or norm_b == 0:
                    return 0.0
                return float(np.dot(a, b) / (norm_a * norm_b))
            
            # 2. Check each sentence's similarity against retrieved chunks
            for s_idx, s_text in enumerate(sentences):
                # Skip trivial sentences (short greetings, transition words, etc.)
                if len(s_text) < 12:
                    continue
                
                s_emb = sentence_embeddings[s_idx]
                max_sim = 0.0
                for c_emb in chunk_embeddings:
                    sim = get_cosine_similarity(s_emb, c_emb)
                    if sim > max_sim:
                        max_sim = sim
                
                logger.info(f"Sentence verification: '{s_text[:40]}...' max_sim={max_sim:.3f}")
                # Threshold is 0.6
                if max_sim < 0.6:
                    unsupported_claims.append(s_text)

            # 3. Add contradiction check
            is_contradicting = self.contradiction_checker.check_contradictions(
                teaching_answer, 
                chunk_texts
            )
            
            # 4. Generate Citations
            citations = self.citation_generator.generate_citations(retrieved_chunks)
            
            # 5. Formulate final verified answer by preserving complete explanation
            verified_sentences = [s for s in sentences if s not in unsupported_claims]
            if len(verified_sentences) >= int(len(sentences) * 0.5) and len(" ".join(verified_sentences).strip()) > 60:
                verified_answer = " ".join(verified_sentences)
            else:
                verified_answer = teaching_answer
            
            status = "Supported"
            if unsupported_claims:
                status = "Unsupported"
            
            warnings = None
            if is_contradicting:
                status = "Unsupported"
                warnings = "WARNING: Direct contradiction detected with curriculum sources."
            elif unsupported_claims:
                warnings = f"WARNING: {len(unsupported_claims)} unsupported sentences were stripped from the explanation."
                
            confidence_percentage = int(100 * (len(verified_sentences) / len(sentences))) if sentences else 100
            if is_contradicting:
                confidence_percentage = min(confidence_percentage, 30)

            execution_time = time.time() - start_time
            result = AgentResult(
                success=True,
                data={
                    "status": status,
                    "reason": f"Verified {len(verified_sentences)}/{len(sentences)} sentences.",
                    "confidence_percentage": confidence_percentage,
                    "warnings": warnings,
                    "citations": citations,
                    "verified_answer": verified_answer,
                    "unsupported_claims": unsupported_claims
                },
                execution_time=execution_time
            )
            
            logger.info(f"FactVerificationAgent completed programmatically: status={status}, confidence={confidence_percentage}%")
            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Exception in FactVerificationAgent: {e}")
            result = AgentResult(
                success=False,
                data=None,
                error=f"Fact verification system exception: {str(e)}",
                execution_time=execution_time
            )
            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )
