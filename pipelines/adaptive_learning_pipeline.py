import time
from loguru import logger
from agentscope.message import UserMsg

from agents.validator_agent import ValidationAgent
from agents.safety_agent import SafetyAgent
from agents.adaptive_learning_agent import AdaptiveLearningAgent
from models.schemas import AgentResult

class AdaptiveLearningPipeline:
    """Orchestrates Validation, Safety, and Adaptive Learning Profiling."""
    def __init__(self) -> None:
        self.validation_agent = ValidationAgent(name="ValAgent")
        self.safety_agent = SafetyAgent(name="SafeAgent")
        self.adaptive_agent = AdaptiveLearningAgent(name="AdaptiveAgent")

    async def run(self, query: str, metadata: dict) -> AgentResult:
        start_time = time.time()
        
        # 1. Validation check
        val_msg = UserMsg(name="Pipeline", content=query, metadata=metadata)
        val_reply = await self.validation_agent.reply(val_msg)
        val_res = getattr(val_reply, "metadata", {}).get("agent_result", {})
        if not val_res.get("success", False):
            return AgentResult(
                success=False,
                error=val_res.get("error", "Sanitization check failed."),
                execution_time=time.time() - start_time
            )

        # 2. Safety check
        safe_msg = UserMsg(name="Pipeline", content=query, metadata=metadata)
        safe_reply = await self.safety_agent.reply(safe_msg)
        safe_res = getattr(safe_reply, "metadata", {}).get("agent_result", {})
        if not safe_res.get("success", False):
            return AgentResult(
                success=False,
                error=safe_res.get("error", "Safety check failed."),
                execution_time=time.time() - start_time
            )

        # 3. Profiling check
        adaptive_msg = UserMsg(name="Pipeline", content=query, metadata=metadata)
        adaptive_reply = await self.adaptive_agent.reply(adaptive_msg)
        adaptive_res = getattr(adaptive_reply, "metadata", {}).get("agent_result", {})
        
        return AgentResult(
            success=adaptive_res.get("success", False),
            data=adaptive_res.get("data"),
            error=adaptive_res.get("error"),
            execution_time=time.time() - start_time
        )
