import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from agents.planner_agent.agents.agent import PlannerAgent
from models.schemas import PlannerResponse

@pytest.mark.asyncio
async def test_eval_planner_intent_classification():
    """Evaluates PlannerAgent intent resolution and structured execution plan."""
    planner = PlannerAgent(name="EvalPlanner")
    
    mock_llm_json = '{"need_quiz": true, "need_story": false, "need_diagram": false, "need_video": true, "need_homework": false, "need_summary": false, "need_revision": false, "need_formula_sheet": false, "need_example": true, "teaching_strategy": "Interactive Quiz and Video Blueprint", "execution_plan": ["RAGAgent", "VideoAgent", "QuizAgent", "TeachingAgent"]}'
    
    with patch.object(planner.gateway, "generate", new=AsyncMock(return_value=mock_llm_json)):
        msg = await planner.reply({
            "content": "Can you explain photosynthesis with a video and give me a quiz?",
            "metadata": {"grade": 6, "subject": "Science"}
        })
        
        agent_result = msg.metadata.get("agent_result", {})
        assert agent_result.get("success") is True, "PlannerAgent execution failed"
        
        data = agent_result.get("data", {})
        planner_resp = PlannerResponse(**data)
        
        assert planner_resp.need_quiz is True, "Planner failed to detect quiz intent"
        assert planner_resp.need_video is True, "Planner failed to detect video intent"
        assert "VideoAgent" in planner_resp.execution_plan, "Planner missing VideoAgent in execution plan"
        assert "QuizAgent" in planner_resp.execution_plan, "Planner missing QuizAgent in execution plan"
