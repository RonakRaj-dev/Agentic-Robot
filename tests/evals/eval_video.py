import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from agents.video_agent.agents.agent import VideoAgent
from models.schemas import VideoAgentResponse

@pytest.mark.asyncio
async def test_eval_video_agent_timestamps_and_blueprint():
    """Evaluates VideoAgent for timestamp sequence continuity, shot types, narration, and scene explanations."""
    video_agent = VideoAgent(name="EvalVideoAgent")
    
    mock_llm_json = '''{
        "topic": "Solar System",
        "class_level": 5,
        "video_title": "Journey Through the Solar System",
        "concept_summary": "An animated tour of planets orbiting the Sun.",
        "total_duration_seconds": 60,
        "structured_prompt": "Cinematic 3D animation of the solar system with bright glowing sun and detailed planetary textures.",
        "scenes": [
            {
                "scene_number": 1,
                "timestamp_start": "00:00",
                "timestamp_end": "00:15",
                "duration_seconds": 15,
                "shot_type": "Wide Establishing 3D Render",
                "visual_prompt": "Camera pans slowly across the glowing Sun with inner rocky planets orbiting in clear trajectories.",
                "narration": "Welcome space explorers! Today we embark on a journey across our solar system.",
                "scene_explanation": "Establishes the solar system layout and introduces planetary motion."
            },
            {
                "scene_number": 2,
                "timestamp_start": "00:15",
                "timestamp_end": "00:30",
                "duration_seconds": 15,
                "shot_type": "Cinematic Close-Up",
                "visual_prompt": "Close-up view of planet Earth showing blue oceans and swirling white clouds.",
                "narration": "Here is our home planet Earth, the third planet from the Sun.",
                "scene_explanation": "Focuses on Earth's atmosphere and liquid water features."
            }
        ],
        "video_url": "https://video.ai-teacher.internal/solar_system"
    }'''
    
    with patch.object(video_agent.gateway, "generate", new=AsyncMock(return_value=mock_llm_json)):
        msg = await video_agent.reply({
            "content": "Create a video for the solar system",
            "metadata": {"grade": 5, "subject": "Science"}
        })
        
        agent_result = msg.metadata.get("agent_result", {})
        assert agent_result.get("success") is True, "VideoAgent execution failed"
        
        data = agent_result.get("data", {})
        video_resp = VideoAgentResponse(**data)
        
        assert video_resp.total_duration_seconds == 60, f"Expected 60s total duration, got {video_resp.total_duration_seconds}"
        assert len(video_resp.scenes) == 2, f"Expected 2 scenes, got {len(video_resp.scenes)}"
        
        s1 = video_resp.scenes[0]
        s2 = video_resp.scenes[1]
        
        assert s1.timestamp_start == "00:00" and s1.timestamp_end == "00:15", f"Scene 1 timestamps invalid: {s1.timestamp_start}-{s1.timestamp_end}"
        assert s2.timestamp_start == "00:15" and s2.timestamp_end == "00:30", f"Scene 2 timestamps invalid: {s2.timestamp_start}-{s2.timestamp_end}"
        assert s1.shot_type != "", "Scene 1 missing shot type"
        assert s1.scene_explanation != "", "Scene 1 missing scene explanation"
