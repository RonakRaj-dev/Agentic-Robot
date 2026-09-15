import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from agentscope.message import Msg, AssistantMsg
from models.schemas import AgentResult

from agents.orchestration import (
    ConcurrentExecutor,
    HandOffManager,
    HandOffSignal,
    GroupChatManager,
    MagneticAttractorEngine,
    OrchestrationEngine,
)


@pytest.mark.asyncio
async def test_concurrent_executor_success():
    executor = ConcurrentExecutor()

    async def mock_task(name: str, delay: float):
        await asyncio.sleep(delay)
        return {"success": True, "data": f"result_{name}"}

    tasks = {
        "branch_a": mock_task("a", 0.05),
        "branch_b": mock_task("b", 0.02),
    }

    res = await executor.execute_parallel(tasks)
    assert res["branch_a"]["success"] is True
    assert res["branch_a"]["data"] == "result_a"
    assert res["branch_b"]["success"] is True
    assert res["branch_b"]["data"] == "result_b"


@pytest.mark.asyncio
async def test_handoff_router_detection_and_execution():
    manager = HandOffManager()
    
    mock_target = MagicMock()
    mock_reply = AssistantMsg(name="ClassroomInteractionAgent", content="Game reply", metadata={})
    mock_target.reply = AsyncMock(return_value=mock_reply)
    
    manager.register_agent("ClassroomInteractionAgent", mock_target)

    signal = manager.detect_handoff(
        query="Start quiz game",
        metadata={"game_mode": "rapid_fire"},
    )
    assert signal is not None
    assert signal.target_agent == "ClassroomInteractionAgent"

    reply = await manager.execute_handoff(signal, "Input")
    assert reply == mock_reply
    mock_target.reply.assert_called_once()


@pytest.mark.asyncio
async def test_group_chat_manager_refinement():
    mock_teaching = MagicMock()
    mock_teaching.reply = AsyncMock(side_effect=[
        AssistantMsg(name="TeachingAgent", content="Initial draft", metadata={"agent_result": {"success": True, "data": {"explanation": "Initial draft"}}}),
        AssistantMsg(name="TeachingAgent", content="Refined draft", metadata={"agent_result": {"success": True, "data": {"explanation": "Refined draft"}}}),
    ])

    mock_adaptive = MagicMock()
    mock_adaptive.reply = AsyncMock(return_value=Msg(name="AdaptiveAgent", content="Please simplify vocabulary for Class 5."))

    group_chat = GroupChatManager(
        teaching_agent=mock_teaching,
        adaptive_agent=mock_adaptive,
        max_rounds=2,
    )

    res = await group_chat.run_lesson_refinement_chat(
        query="What is photosynthesis?",
        context_str="Plants use sunlight to make food.",
        adaptive_data={"difficulty_level": "Beginner"},
        pipeline_metadata={"session_id": "test_sess", "grade": 5},
    )

    assert res["consensus_reached"] is True
    assert res["final_explanation"] == "Refined draft"
    assert res["chat_rounds"] == 3


@pytest.mark.asyncio
async def test_magnetic_attractor_engine_convergence():
    mock_teaching = MagicMock()
    mock_teaching.reply = AsyncMock(return_value=AssistantMsg(
        name="TeachingAgent",
        content="Corrected grounded draft",
        metadata={"agent_result": {"success": True, "data": {"explanation": "Corrected grounded draft"}}}
    ))

    mock_verify = MagicMock()
    mock_verify.reply = AsyncMock(side_effect=[
        AssistantMsg(name="VerifyAgent", content="Partial support", metadata={"agent_result": {
            "success": True,
            "data": {
                "confidence_percentage": 50,
                "unsupported_claims": ["Photosynthesis produces gold."],
                "verified_answer": "Plants make food."
            }
        }}),
        AssistantMsg(name="VerifyAgent", content="Full support", metadata={"agent_result": {
            "success": True,
            "data": {
                "confidence_percentage": 95,
                "unsupported_claims": [],
                "verified_answer": "Corrected grounded draft"
            }
        }}),
    ])

    attractor = MagneticAttractorEngine(
        teaching_agent=mock_teaching,
        verification_agent=mock_verify,
        target_groundedness=0.85,
        max_attractor_attempts=2,
    )

    res = await attractor.converge_explanation_attractor(
        initial_explanation="Photosynthesis produces gold.",
        retrieved_chunks=[{"chunk_text": "Plants use light to make sugar."}],
        grounded_query="What is photosynthesis?",
        pipeline_metadata={"session_id": "test_sess"},
    )

    assert res["converged"] is True
    assert res["attractor_attempts"] == 2
    assert res["final_explanation"] == "Corrected grounded draft"
