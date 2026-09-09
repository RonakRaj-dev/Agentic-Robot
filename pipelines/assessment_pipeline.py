import time
from loguru import logger
from agentscope.message import UserMsg

from agents.assessment_agent.agents import AssessmentAgent
from models.schemas import AgentResult

class AssessmentPipeline:
    """Orchestrates generating assessment questions and evaluating student answers."""
    def __init__(self) -> None:
        self.assessment_agent = AssessmentAgent(name="AssessmentAgent")

    async def run_generate(self, topic: str, metadata: dict) -> AgentResult:
        start_time = time.time()
        meta = dict(metadata)
        meta["action"] = "generate"
        
        msg = UserMsg(name="Pipeline", content=topic, metadata=meta)
        reply = await self.assessment_agent.reply(msg)
        res = getattr(reply, "metadata", {}).get("agent_result", {})
        
        return AgentResult(
            success=res.get("success", False),
            data=res.get("data"),
            error=res.get("error"),
            execution_time=time.time() - start_time
        )

    async def run_evaluate(self, topic: str, student_answers: dict, original_questions: list, metadata: dict) -> AgentResult:
        start_time = time.time()
        meta = dict(metadata)
        meta["action"] = "evaluate"
        meta["student_answers"] = student_answers
        meta["original_questions"] = original_questions
        
        msg = UserMsg(name="Pipeline", content=topic, metadata=meta)
        reply = await self.assessment_agent.reply(msg)
        res = getattr(reply, "metadata", {}).get("agent_result", {})
        
        return AgentResult(
            success=res.get("success", False),
            data=res.get("data"),
            error=res.get("error"),
            execution_time=time.time() - start_time
        )
