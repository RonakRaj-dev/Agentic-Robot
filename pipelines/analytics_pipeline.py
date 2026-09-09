import time
from loguru import logger
from agentscope.message import UserMsg

from agents.analytics_agent import AnalyticsAgent
from models.schemas import AgentResult

class AnalyticsPipeline:
    """Orchestrates classroom learning diagnostics and progress logging."""
    def __init__(self) -> None:
        self.analytics_agent = AnalyticsAgent(name="AnalyticsAgent")

    async def compile_report(self, query: str, metadata: dict) -> AgentResult:
        start_time = time.time()
        
        msg = UserMsg(name="Pipeline", content=query, metadata=metadata)
        reply = await self.analytics_agent.reply(msg)
        res = getattr(reply, "metadata", {}).get("agent_result", {})
        
        return AgentResult(
            success=res.get("success", False),
            data=res.get("data"),
            error=res.get("error"),
            execution_time=time.time() - start_time
        )
