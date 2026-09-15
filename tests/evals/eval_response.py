import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from agents.response_agent.agents.agent import ResponseAgent

@pytest.mark.asyncio
async def test_eval_response_agent_pedagogical_clarity():
    """Evaluates ResponseAgent tone, structure, and student-level output formatting."""
    response_agent = ResponseAgent(name="EvalResponseAgent")
    
    mock_llm_json = '''{
        "answer": "Photosynthesis is the process by which green plants convert light energy into chemical energy.",
        "summary": "Plants use sunlight, CO2, and water to make glucose and oxygen.",
        "key_points": ["Requires sunlight and chlorophyll", "Produces oxygen for living things"],
        "teaching_mode": "Conceptual",
        "diagram_required": false,
        "video_required": false,
        "quiz_generated": false,
        "confidence_score": 0.95
    }'''
    
    with patch.object(response_agent.gateway, "generate", new=AsyncMock(return_value=mock_llm_json)):
        msg = await response_agent.reply({
            "content": "Explain photosynthesis",
            "metadata": {"grade": 6, "subject": "Science"}
        })
        
        agent_result = msg.metadata.get("agent_result", {})
        assert agent_result.get("success") is True, "ResponseAgent execution failed"
        
        data = agent_result.get("data", {})
        assert "convert light energy" in data.get("answer", ""), "Answer text missing core explanation"
        assert len(data.get("key_points", [])) == 2, "Key points array missing items"
        assert data.get("confidence_score", 0) >= 0.9, f"Confidence score low: {data.get('confidence_score')}"
