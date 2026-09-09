import time
from loguru import logger
from agentscope.message import UserMsg

from agents.content_generation_agent import ContentGenerationAgent
from models.schemas import AgentResult

class HomeworkPipeline:
    """Orchestrates generation of revision sheets, homework, handouts, and flashcards."""
    def __init__(self) -> None:
        self.generator_agent = ContentGenerationAgent(name="ContentGenAgent")

    async def generate_material(
        self,
        topic: str,
        material_type: str,
        format_type: str,
        metadata: dict
    ) -> AgentResult:
        start_time = time.time()
        meta = dict(metadata)
        meta["material_type"] = material_type
        meta["format"] = format_type
        
        msg = UserMsg(name="Pipeline", content=topic, metadata=meta)
        reply = await self.generator_agent.reply(msg)
        res = getattr(reply, "metadata", {}).get("agent_result", {})
        
        return AgentResult(
            success=res.get("success", False),
            data=res.get("data"),
            error=res.get("error"),
            execution_time=time.time() - start_time
        )
