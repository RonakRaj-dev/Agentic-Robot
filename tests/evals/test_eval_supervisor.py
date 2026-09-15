import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from agents.supervisor_agent_v3.agents.agent import ClassroomSupervisorAgentV3

@pytest.mark.asyncio
async def test_eval_supervisor_v3_orchestration_latency():
    """Evaluates ClassroomSupervisorAgentV3 end-to-end orchestration and latency budget."""
    mock_reply = AsyncMock()
    mock_reply.metadata = {
        "agent_result": {
            "success": True,
            "data": {
                "answer": "Photosynthesis is how plants make food.",
                "summary": "Plants use light, water, and air.",
                "key_points": ["Sunlight", "Water", "CO2"],
                "confidence_score": 0.9
            }
        }
    }
    
    with patch("agents.retrieval.curriculum_rag_agent.RetrievalPipeline"), \
         patch("ai_teacher_robot.repositories.interaction_repository.InteractionRepository"), \
         patch("ai_teacher_robot.repositories.v3_repositories.LearningHistoryRepository"):
        supervisor = ClassroomSupervisorAgentV3(name="EvalSupervisorV3")
        
        with patch.object(supervisor.session_manager, "acquire_lock", return_value=True), \
             patch.object(supervisor.session_manager, "save_message", return_value=None), \
             patch.object(supervisor.session_manager, "release_lock", return_value=None), \
             patch.object(supervisor.orchestrator, "execute_sequential_guardrails", new=AsyncMock(return_value=(True, None))), \
             patch.object(supervisor.orchestrator, "execute_concurrent_prefetch", new=AsyncMock(return_value={
                 "planner": {"data": {"execution_plan": ["TeachingAgent"], "need_quiz": False}},
                 "adaptive": {"data": {"difficulty_level": "Intermediate", "teaching_style": "Conceptual"}},
                 "memory": {"data": {"working_memory": "", "long_term_memory": ""}}
             })), \
             patch.object(supervisor.rag_agent, "reply", new=AsyncMock(return_value=AsyncMock(metadata={"agent_result": {"success": True, "data": {"chunks": []}}}))), \
             patch.object(supervisor.teaching_agent, "reply", new=AsyncMock(return_value=mock_reply)), \
             patch.object(supervisor.learning_repo, "update_mastery", new=AsyncMock(return_value=None)), \
             patch.object(supervisor.interaction_repo, "log_interaction", new=AsyncMock(return_value=None)):
            
            start_t = asyncio.get_event_loop().time()
            msg = await supervisor.reply({
                "content": "Explain photosynthesis to a class 6 student",
                "metadata": {"session_id": "eval_sup_sess", "grade": 6, "subject": "Science"}
            })
            elapsed = asyncio.get_event_loop().time() - start_t
            
            agent_result = msg.metadata.get("agent_result", {})
            assert agent_result.get("success") is True, "SupervisorV3 end-to-end failed"
            assert elapsed < 5.0, f"Supervisor execution exceeded latency budget: {elapsed:.2f}s"
