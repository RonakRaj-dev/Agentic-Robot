import time
import json
import os
from typing import Any
import models.compat

from loguru import logger
from agentscope.agent import Agent
from agentscope.message import Msg

from models.llm_gateway import LLMGateway
from state.agentState import AgentStateManager
from models.schemas import AgentResult, ContentGenerationResponse, get_content_str
from ai_teacher_robot.repositories.v3_repositories import GeneratedMaterialsRepository
from .prompts import build_content_generation_prompt


class ContentGenerationAgent(Agent):
    """
    ContentGenerationAgent: Creates teaching aids (worksheets, flashcards, mind maps)
    in various export formats (markdown, html, pdf, ppt).
    """
    def __init__(self, name: str = "ContentGenerationAgent", **kwargs: Any) -> None:
        super().__init__()
        self.name = name
        self.state_manager = AgentStateManager()
        from .. import LLMGateway
        self.gateway = LLMGateway()
        self.materials_repo = GeneratedMaterialsRepository()

    async def reply(self, x: Any = None) -> Msg:
        start_time = time.time()
        query = get_content_str(x)
        
        session_id = "default_sess"
        metadata = {}
        if isinstance(x, dict):
            metadata = x.get("metadata", {})
            session_id = metadata.get("session_id", "default_sess")
        elif hasattr(x, "metadata"):
            metadata = getattr(x, "metadata", {}) or {}
            session_id = metadata.get("session_id", "default_sess")

        teacher_id = metadata.get("teacher_id") or metadata.get("username") or "default_teacher"
        grade = metadata.get("grade") or 5
        subject = metadata.get("subject") or "General"
        material_type = metadata.get("material_type", "worksheet")
        format_type = metadata.get("format", "markdown")

        try:
            prompt = build_content_generation_prompt(
                query=query,
                grade=grade,
                subject=subject,
                material_type=material_type,
                format_type=format_type,
            )

            model_config = self.state_manager.get_model_config("ContentGenerationAgent")
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
            response_obj = ContentGenerationResponse(**parsed_data)

            local_filename = f"generated_{material_type}_{int(time.time())}.{format_type[:3]}"
            local_path = os.path.join("state", local_filename)
            try:
                os.makedirs("state", exist_ok=True)
                with open(local_path, "w", encoding="utf-8") as f:
                    f.write(response_obj.content)
                response_obj.file_path = local_path
            except Exception as e:
                logger.warning(f"Could not write local content file: {e}")

            await self.materials_repo.log_material(
                teacher_id=teacher_id,
                grade=grade,
                subject=subject,
                topic=query,
                material_type=material_type,
                format_type=format_type,
                content=response_obj.content,
                file_path=response_obj.file_path
            )

            execution_time = time.time() - start_time
            result = AgentResult(
                success=True,
                data=response_obj.model_dump(),
                execution_time=execution_time
            )

            logger.info(f"ContentGenerationAgent successfully created {material_type} for teacher {teacher_id}")

            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Exception in ContentGenerationAgent: {e}")
            result = AgentResult(
                success=False,
                data=None,
                error=f"Content generation exception: {str(e)}",
                execution_time=execution_time
            )
            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )
