import time
import json
import re
from typing import Any
import models.compat

from loguru import logger
from agentscope.agent import Agent
from agentscope.message import Msg

from .. import LLMGateway
from state.agentState import AgentStateManager
from models.schemas import AgentResult, VideoAgentResponse, VideoScenePrompt, get_content_str
from .prompts import build_video_prompt


class VideoAgent(Agent):
    """
    Video Agent: Generates structured video scripts, visual prompts, and video payloads
    adapted to the specific student class grade level.
    """
    def __init__(self, name: str = "VideoAgent", **kwargs: Any) -> None:
        super().__init__()
        self.name = name
        self.state_manager = AgentStateManager()
        from .. import LLMGateway
        self.gateway = LLMGateway()

    async def reply(self, x: Any = None) -> Msg:
        start_time = time.time()
        raw_query = get_content_str(x)

        session_id = "default_sess"
        metadata = {}
        if isinstance(x, dict):
            metadata = x.get("metadata", {})
            session_id = metadata.get("session_id", "default_sess")
        elif hasattr(x, "metadata"):
            metadata = getattr(x, "metadata", {}) or {}
            session_id = metadata.get("session_id", "default_sess")

        topic = raw_query.strip() or "Educational Topic"
        grade_val = metadata.get("grade") or metadata.get("class") or metadata.get("planner_result", {}).get("class") or 5
        subject = metadata.get("subject") or metadata.get("planner_result", {}).get("subject") or "General Science"

        grade = 5
        if grade_val is not None:
            match = re.search(r'\d+', str(grade_val))
            if match:
                grade = int(match.group(0))

        try:
            class_prompt = self.state_manager.get_class_subject_prompt(grade, subject)

            chapter_title = metadata.get("chapter") or metadata.get("chapter_title") or topic
            prompt = build_video_prompt(
                class_prompt=class_prompt,
                grade=grade,
                topic=topic,
                subject=subject,
                chapter_title=chapter_title
            )


            model_config = self.state_manager.get_model_config("VideoAgent")
            if not model_config:
                model_config = {"temperature": 0.3, "max_tokens": 800}
            model_config = dict(model_config)
            model_config["response_format"] = {"type": "json_object"}

            raw_response = await self.gateway.generate(prompt, **model_config)

            cleaned = raw_response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            parsed_data = json.loads(cleaned)
            
            # Ensure visualStyle, cameraMotion, masterPrompt and scene aliases are hydrated
            if "visual_style" not in parsed_data:
                parsed_data["visual_style"] = "3D Pixar Educational Animation" if grade <= 5 else "3D Photorealistic Infographic"
            parsed_data["visualStyle"] = parsed_data.get("visualStyle") or parsed_data["visual_style"]
            
            if "camera_motion" not in parsed_data:
                parsed_data["camera_motion"] = "Dynamic orbital pan with depth of field"
            parsed_data["cameraMotion"] = parsed_data.get("cameraMotion") or parsed_data["camera_motion"]
            
            if "structured_prompt" not in parsed_data:
                parsed_data["structured_prompt"] = f"Cinematic 3D animation detailing {topic} for Class {grade} {subject} students. 4K studio render with volumetric lighting."
            parsed_data["masterPrompt"] = parsed_data.get("masterPrompt") or parsed_data["structured_prompt"]
            
            if "scenes" in parsed_data and isinstance(parsed_data["scenes"], list):
                for idx, sc in enumerate(parsed_data["scenes"], 1):
                    if isinstance(sc, dict):
                        sc["scene_number"] = sc.get("scene_number") or sc.get("scene") or idx
                        sc["scene"] = sc["scene_number"]
                        sc["visual_prompt"] = sc.get("visual_prompt") or sc.get("action") or f"3D animation visualizing {topic}"
                        sc["action"] = sc["visual_prompt"]
                        sc["narration"] = sc.get("narration") or sc.get("script") or f"Let's explore {topic}!"
                        sc["script"] = sc["narration"]

            video_response = VideoAgentResponse(**parsed_data)

            execution_time = time.time() - start_time
            result = AgentResult(
                success=True,
                data=video_response.model_dump(),
                execution_time=execution_time
            )


            logger.info(
                "VideoAgent generated video script payload successfully",
                agent=self.name,
                topic=topic,
                execution_time=round(execution_time, 3),
                session_id=session_id
            )

            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                "Exception in VideoAgent: {}",
                str(e),
                agent=self.name,
                execution_time=round(execution_time, 3),
                session_id=session_id
            )
            result = AgentResult(
                success=False,
                data=None,
                error=f"Video generation exception: {str(e)}",
                execution_time=execution_time
            )
            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )
