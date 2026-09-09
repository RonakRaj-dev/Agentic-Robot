import time
from loguru import logger
from agentscope.message import UserMsg

from agents.classroom_interaction_agent import ClassroomInteractionAgent
from models.schemas import AgentResult

class ClassroomPipeline:
    """Orchestrates classroom game modes and interaction turns."""
    def __init__(self) -> None:
        self.interaction_agent = ClassroomInteractionAgent(name="ClassInteractionAgent")

    async def run_turn(self, query: str, game_mode: str, score: int, metadata: dict) -> AgentResult:
        start_time = time.time()
        meta = dict(metadata)
        meta["game_mode"] = game_mode
        meta["score"] = score
        
        msg = UserMsg(name="Pipeline", content=query, metadata=meta)
        reply = await self.interaction_agent.reply(msg)
        res = getattr(reply, "metadata", {}).get("agent_result", {})
        
        return AgentResult(
            success=res.get("success", False),
            data=res.get("data"),
            error=res.get("error"),
            execution_time=time.time() - start_time
        )
