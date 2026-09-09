import os
import sys
import time
import asyncio
from dotenv import load_dotenv

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath("."))

load_dotenv()

from loguru import logger
from state.agentState import AgentStateManager
from models.llm_gateway import LLMGateway
from ai_teacher_robot.rag.embedding.embedding_generator import EmbeddingGenerator
from agents.retrieval.reranker import Reranker
from agents.memory_agent import MemoryAgent
from agents.supervisor_agent_v3 import ClassroomSupervisorAgentV3
from agentscope.message import Msg

async def test_all():
    print("=" * 60)
    print("1. Testing AgentStateManager Configuration Loading")
    print("=" * 60)
    asm = AgentStateManager()
    for name in ["PlannerAgent", "AdaptiveLearningAgent", "TeachingAgent", "MemoryAgent", "CurriculumRAGAgent", "ResponseAgent"]:
        cfg = asm.load_agent_config(name)
        print(f"[{name}] -> Loaded successfully with keys: {list(cfg.keys())}")

    print("\n" + "=" * 60)
    print("2. Testing Shared Singletons for Embedding & Reranker")
    print("=" * 60)
    t0 = time.time()
    emb_gen1 = EmbeddingGenerator()
    emb1 = emb_gen1._get_model()
    t_emb1 = time.time() - t0
    print(f"EmbeddingGenerator 1st load: {t_emb1:.3f}s (model: {emb1 is not None})")

    t0 = time.time()
    emb_gen2 = EmbeddingGenerator()
    emb2 = emb_gen2._get_model()
    t_emb2 = time.time() - t0
    print(f"EmbeddingGenerator 2nd load (Singleton): {t_emb2:.4f}s (same instance: {emb1 is emb2})")

    t0 = time.time()
    reranker1 = Reranker()
    r1 = reranker1._get_model()
    t_r1 = time.time() - t0
    print(f"Reranker 1st load: {t_r1:.3f}s (model: {r1 is not None})")

    t0 = time.time()
    reranker2 = Reranker()
    r2 = reranker2._get_model()
    t_r2 = time.time() - t0
    print(f"Reranker 2nd load (Singleton): {t_r2:.4f}s (same instance: {r1 is r2})")

    print("\n" + "=" * 60)
    print("3. Testing LLMGateway with openai/gpt-oss-120b")
    print("=" * 60)
    gateway = LLMGateway(force_reload=True)
    t0 = time.time()
    resp = await gateway.generate("Explain what hemoglobin does in 1 concise sentence.", response_format={"type": "json_object"})
    t_gw = time.time() - t0
    print(f"LLM Gateway JSON generated in {t_gw:.3f}s:\n{resp}")

    print("\n" + "=" * 60)
    print("4. Testing MemoryAgent Execution")
    print("=" * 60)
    mem_agent = MemoryAgent()
    t0 = time.time()
    mem_msg = await mem_agent.reply({"metadata": {"session_id": "test_sess", "student_id": "test_student"}})
    t_mem = time.time() - t0
    print(f"MemoryAgent completed in {t_mem:.3f}s -> Content:\n{mem_msg.content}")

    print("\n" + "=" * 60)
    print("5. Testing Full SupervisorV3 End-to-End Query")
    print("=" * 60)
    sup = ClassroomSupervisorAgentV3()
    test_query = "[Chapter: Chapter 8: A Treat for Mosquitoes] Why do doctors recommend checking blood reports for hemoglobin levels, and what advice did Aarti receive in the chapter to cure her anemia?"
    msg = Msg(
        name="Student",
        content=test_query,
        metadata={
            "session_id": "verify_sess_123",
            "grade": 5,
            "subject": "Our_Wondorous_World",
            "chapter": "Chapter 8: A Treat for Mosquitoes",
            "student_id": "verify_student"
        }
    )
    t0 = time.time()
    sup_reply = await sup.reply(msg)
    t_sup = time.time() - t0
    print(f"\nSupervisor V3 full execution time: {t_sup:.3f}s")
    
    import json
    result_meta = getattr(sup_reply, "metadata", {}).get("agent_result", {})
    data = result_meta.get("data", {})
    print("\nFINAL ANSWER DELIVERED TO STUDENT:")
    print("-" * 50)
    print(data.get("answer"))
    print("-" * 50)
    print(f"Confidence score: {data.get('confidence_score')}")
    print(f"Citations count: {len(data.get('citations', []))}")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_all())
