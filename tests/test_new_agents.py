import pytest
import json
import asyncio
from unittest.mock import AsyncMock, patch

from agents.quiz_agent import QuizAgent
from agents.video_agent import VideoAgent
from agents.supervisor_agent_v2 import ClassroomSupervisorAgentV2
from state.agentState import AgentStateManager
from models.schemas import QuizCardResponse, VideoAgentResponse

@pytest.mark.asyncio
async def test_agent_state_manager_md_prompts():
    manager = AgentStateManager()
    prompt_c4 = manager.get_class_subject_prompt(4, "Social Studies")
    assert "Class 4" in prompt_c4
    assert "Social Studies" in prompt_c4

    prompt_c10 = manager.get_class_subject_prompt(10, "Science")
    assert "Class 10" in prompt_c10 or "Board" in prompt_c10

@pytest.mark.asyncio
async def test_quiz_agent_flag_card_generation():
    quiz_agent = QuizAgent(name="TestQuizAgent")
    
    mock_llm_json = json.dumps({
        "card_type": "flag_quiz_card",
        "question_id": "quiz_test123",
        "question": "Which type of soil is predominantly found in northern plains of India?",
        "options": [
            {"key": "A", "text": "Alluvial Soil"},
            {"key": "B", "text": "Black Soil"},
            {"key": "C", "text": "Red Soil"},
            {"key": "D", "text": "Desert Soil"}
        ],
        "correct_option": "A",
        "explanation": "Alluvial soil is deposited by rivers in the northern plains.",
        "difficulty": "Medium",
        "class_level": 4,
        "subject": "Social Studies"
    })

    with patch.object(quiz_agent.gateway, "generate", new=AsyncMock(return_value=mock_llm_json)):
        msg = await quiz_agent.reply({"content": "Give me a quiz on northern plains", "metadata": {"grade": 4, "subject": "Social Studies"}})
        res_data = msg.metadata["agent_result"]
        assert res_data["success"] is True
        data = res_data["data"]
        assert data["card_type"] == "flag_quiz_card_set"
        card = data["cards"][0]
        assert len(card["options"]) == 4
        assert card["correct_option"] == "A"

@pytest.mark.asyncio
async def test_video_agent_generation():
    video_agent = VideoAgent(name="TestVideoAgent")

    mock_llm_json = json.dumps({
        "topic": "Photosynthesis",
        "class_level": 5,
        "video_title": "The Wonder of Plant Food: Photosynthesis",
        "concept_summary": "Explains how green plants make their food using sunlight, water, and air.",
        "structured_prompt": "3D animated video showing a sunny garden with green plant leaves absorbing light.",
        "scenes": [
            {
                "scene_number": 1,
                "narration": "Welcome kids! Have you ever wondered how plants eat?",
                "visual_prompt": "Close-up of bright green leaves glowing under golden sunlight."
            }
        ],
        "video_url": "https://video.ai-teacher.internal/photosynthesis"
    })

    with patch.object(video_agent.gateway, "generate", new=AsyncMock(return_value=mock_llm_json)):
        msg = await video_agent.reply({"content": "Make a video for photosynthesis", "metadata": {"grade": 5, "subject": "Science"}})
        res_data = msg.metadata["agent_result"]
        assert res_data["success"] is True
        data = res_data["data"]
        assert data["topic"] == "Photosynthesis"
        assert len(data["scenes"]) == 1

@pytest.mark.asyncio
async def test_supervisor_v2_quiz_routing():
    supervisor = ClassroomSupervisorAgentV2(name="TestSupervisor")

    mock_quiz_reply = AsyncMock()
    mock_quiz_reply.metadata = {
        "agent_result": {
            "success": True,
            "data": {"card_type": "flag_quiz_card", "question": "Sample quiz question"}
        }
    }
    supervisor.quiz_agent.reply = mock_quiz_reply

    with patch.object(supervisor.validation_agent, "reply", new=AsyncMock(return_value=AsyncMock(metadata={"agent_result": {"success": True}}))), \
         patch.object(supervisor.safety_agent, "reply", new=AsyncMock(return_value=AsyncMock(metadata={"agent_result": {"success": True}}))):
        
        reply = await supervisor.reply({"content": "Generate a quiz card for class 4 maths", "metadata": {"session_id": "test_quiz_sess"}})
        assert mock_quiz_reply.called
