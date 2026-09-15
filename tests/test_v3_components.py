import os
import json
import pytest
import datetime
from unittest.mock import MagicMock, patch, AsyncMock

from models.schemas import AgentResult
from state.sessionState import SessionStateManager
from state.agentState import AgentStateManager

# V3 Agents
from agents.adaptive_learning_agent import AdaptiveLearningAgent
from agents.planner_agent import PlannerAgent
from agents.assessment_agent.agents import AssessmentAgent
from agents.classroom_interaction_agent import ClassroomInteractionAgent
from agents.content_generation_agent import ContentGenerationAgent
from agents.summary_agent import SummaryAgent
from agents.analytics_agent import AnalyticsAgent
from agents.memory_agent import MemoryAgent
from agents.supervisor_agent_v3 import ClassroomSupervisorAgentV3

from agentscope.message import UserMsg, TextBlock

@pytest.fixture(autouse=True)
def setup_env():
    """Sets up clean test environments."""
    from state.sessionState import SessionStateManager
    SessionStateManager._instance = None
    os.environ["GROQ_API_KEY"] = "mock-groq-key"
    os.environ["MONGO_URI"] = "mongodb://127.0.0.1:9999"
    yield
    SessionStateManager._instance = None

@pytest.mark.anyio
@patch("agents.adaptive_learning_agent.LLMGateway")
async def test_adaptive_learning_agent(mock_gw):
    # Set mock response
    mock_response = {
        "difficulty_level": "Beginner",
        "teaching_style": "Visual",
        "recommended_learning_path": ["basic physics", "forces"]
    }
    mock_gw.return_value.generate = AsyncMock(return_value=json.dumps(mock_response))

    agent = AdaptiveLearningAgent(name="AdaptiveAgent")
    msg = UserMsg(name="Student", content="Explain gravity", metadata={"student_id": "test_user"})
    
    reply = await agent.reply(msg)
    res = getattr(reply, "metadata", {}).get("agent_result", {})
    
    assert res["success"] is True
    assert res["data"]["difficulty_level"] == "Beginner"
    assert "forces" in res["data"]["recommended_learning_path"]

@pytest.mark.anyio
@patch("agents.planner_agent.LLMGateway")
async def test_planner_agent(mock_gw):
    mock_response = {
        "need_quiz": True,
        "need_story": False,
        "need_diagram": True,
        "need_video": False,
        "need_homework": True,
        "need_summary": False,
        "need_revision": False,
        "need_formula_sheet": False,
        "need_example": False,
        "teaching_strategy": "Direct explanation then testing",
        "execution_plan": ["TeachingAgent", "AssessmentAgent"]
    }
    mock_gw.return_value.generate = AsyncMock(return_value=json.dumps(mock_response))

    agent = PlannerAgent(name="PlannerAgent")
    msg = UserMsg(name="Supervisor", content="I want to learn about Newton's laws")
    
    reply = await agent.reply(msg)
    res = getattr(reply, "metadata", {}).get("agent_result", {})
    
    assert res["success"] is True
    assert res["data"]["need_quiz"] is True
    assert "AssessmentAgent" in res["data"]["execution_plan"]

@pytest.mark.anyio
@patch("agents.assessment_agent.LLMGateway")
async def test_assessment_agent_generate(mock_gw):
    mock_response = {
        "questions": [
            {
                "question_id": "q1",
                "type": "mcq",
                "question_text": "What goes up must come down?",
                "options": [
                    {"key": "A", "text": "Gravity"},
                    {"key": "B", "text": "Buoyancy"}
                ],
                "correct_answer": "A",
                "explanation": "Gravity pulls objects down.",
                "difficulty": "Easy"
            }
        ]
    }
    mock_gw.return_value.generate = AsyncMock(return_value=json.dumps(mock_response))

    agent = AssessmentAgent(name="AssessmentAgent")
    msg = UserMsg(name="Supervisor", content="gravity", metadata={"action": "generate"})
    
    reply = await agent.reply(msg)
    res = getattr(reply, "metadata", {}).get("agent_result", {})
    
    assert res["success"] is True
    assert len(res["data"]["questions"]) == 1
    assert res["data"]["questions"][0]["type"] == "mcq"

@pytest.mark.anyio
@patch("agents.classroom_interaction_agent.LLMGateway")
async def test_classroom_interaction_agent(mock_gw):
    mock_response = {
        "game_mode": "Rapid Fire",
        "timer_seconds": 15,
        "score": 3,
        "leaderboard": [{"name": "student1", "score": 3}],
        "hints": ["Starts with G"],
        "game_payload": {"question": "What pulls objects to Earth?"}
    }
    mock_gw.return_value.generate = AsyncMock(return_value=json.dumps(mock_response))

    agent = ClassroomInteractionAgent(name="ClassInteractionAgent")
    msg = UserMsg(name="Supervisor", content="Gravity", metadata={"game_mode": "Rapid Fire", "score": 2})
    
    reply = await agent.reply(msg)
    res = getattr(reply, "metadata", {}).get("agent_result", {})
    
    assert res["success"] is True
    assert res["data"]["score"] == 3
    assert "Starts with G" in res["data"]["hints"]

@pytest.mark.anyio
@patch("agents.content_generation_agent.LLMGateway")
async def test_content_generation_agent(mock_gw):
    mock_response = {
        "material_type": "handout",
        "format": "markdown",
        "content": "# Gravity Handout\nThis is a sheet detailing gravity.",
        "file_path": "state/test_handout.md"
    }
    mock_gw.return_value.generate = AsyncMock(return_value=json.dumps(mock_response))

    agent = ContentGenerationAgent(name="ContentGenAgent")
    msg = UserMsg(name="Supervisor", content="gravity", metadata={"material_type": "handout", "format": "markdown"})
    
    reply = await agent.reply(msg)
    res = getattr(reply, "metadata", {}).get("agent_result", {})
    
    assert res["success"] is True
    assert "# Gravity Handout" in res["data"]["content"]

@pytest.mark.anyio
@patch("agents.summary_agent.LLMGateway")
async def test_summary_agent(mock_gw):
    mock_response = {
        "topics_covered": ["Gravity", "Weight"],
        "key_concepts": ["Weight is mass times gravity acceleration"],
        "formula_revision": ["W = m * g"],
        "interesting_fact": "Gravity on Jupiter is stronger than Earth.",
        "quote_of_day": "Keep pulling ahead.",
        "homework": ["Calculate your weight on the Moon."],
        "next_topic": "Friction"
    }
    mock_gw.return_value.generate = AsyncMock(return_value=json.dumps(mock_response))

    agent = SummaryAgent(name="SummaryAgent")
    msg = UserMsg(name="Supervisor", content="We studied gravity and weight today.")
    
    reply = await agent.reply(msg)
    res = getattr(reply, "metadata", {}).get("agent_result", {})
    
    assert res["success"] is True
    assert "Friction" in res["data"]["next_topic"]
    assert "W = m * g" in res["data"]["formula_revision"]

@pytest.mark.anyio
@patch("agents.validator_agent.LLMGateway")
@patch("agents.safety_agent.LLMGateway")
@patch("agents.memory_agent.LLMGateway")
@patch("agents.adaptive_learning_agent.LLMGateway")
@patch("agents.planner_agent.LLMGateway")
@patch("agents.teaching_agent.LLMGateway")
@patch("agents.response_agent.LLMGateway")
async def test_supervisor_v3_integration(
    mock_resp_gw, mock_teach_gw, mock_plan_gw, mock_adap_gw, mock_mem_gw, mock_safety_gw, mock_val_gw
):
    # Set mock responses for each agent in the supervisor pipeline
    mock_val_gw.return_value.generate = AsyncMock(return_value='{"valid": true, "reason": ""}')
    mock_safety_gw.return_value.generate = AsyncMock(return_value='{"safe": true, "reason": ""}')
    
    mem_resp = {
        "working_memory": "Forces",
        "session_memory": "Forces",
        "long_term_memory": "No struggles",
        "curriculum_memory": "NCERT alignment"
    }
    mock_mem_gw.return_value.generate = AsyncMock(return_value=json.dumps(mem_resp))

    adap_resp = {
        "difficulty_level": "Intermediate",
        "teaching_style": "Conceptual",
        "recommended_learning_path": ["Friction forces"]
    }
    mock_adap_gw.return_value.generate = AsyncMock(return_value=json.dumps(adap_resp))

    plan_resp = {
        "need_quiz": False,
        "need_story": False,
        "need_diagram": False,
        "need_video": False,
        "need_homework": False,
        "need_summary": False,
        "need_revision": False,
        "need_formula_sheet": False,
        "need_example": False,
        "teaching_strategy": "Explain force concepts.",
        "execution_plan": ["TeachingAgent"]
    }
    mock_plan_gw.return_value.generate = AsyncMock(return_value=json.dumps(plan_resp))

    mock_teach_gw.return_value.generate = AsyncMock(return_value="A force is a push or a pull.")

    resp_payload = {
        "answer": "A force is a push or a pull.",
        "summary": "Force summary description",
        "key_points": ["push", "pull"],
        "teaching_mode": "Conceptual",
        "diagram_required": False,
        "video_required": False,
        "quiz_generated": False,
        "confidence_score": 0.9
    }
    mock_resp_gw.return_value.generate = AsyncMock(return_value=json.dumps(resp_payload))

    supervisor = ClassroomSupervisorAgentV3(name="SupervisorV3")
    msg = UserMsg(
        name="Student", 
        content="What is a force?", 
        metadata={"session_id": "test_v3_integration", "student_id": "student_ronak", "grade": 9, "subject": "Science"}
    )
    
    reply = await supervisor.reply(msg)
    res = getattr(reply, "metadata", {}).get("agent_result", {})
    
    assert res["success"] is True
    assert res["data"]["answer"] == "A force is a push or a pull."
    assert res["data"]["adaptive_profile"]["difficulty_level"] == "Intermediate"
    assert res["data"]["planning_strategy"] == "Explain force concepts."
