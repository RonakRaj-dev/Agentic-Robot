import time
from loguru import logger
from agentscope.message import UserMsg

from agents.summary_agent import SummaryAgent
from models.schemas import AgentResult

class SummaryPipeline:
    """Orchestrates creating end-of-class reviews and takeaways summaries."""
    def __init__(self) -> None:
        self.summary_agent = SummaryAgent(name="SummaryAgent")

    async def run_summary(self, session_context_summary: str, metadata: dict) -> AgentResult:
        start_time = time.time()
        
        msg = UserMsg(name="Pipeline", content=session_context_summary, metadata=metadata)
        reply = await self.summary_agent.reply(msg)
        res = getattr(reply, "metadata", {}).get("agent_result", {})
        
        return AgentResult(
            success=res.get("success", False),
            data=res.get("data"),
            error=res.get("error"),
            execution_time=time.time() - start_time
        )
