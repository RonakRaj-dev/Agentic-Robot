import time
from typing import Any, Dict, Optional, Callable
from pydantic import BaseModel, Field
from loguru import logger
from agentscope.message import Msg


class HandOffSignal(BaseModel):
    """
    Signal emitted by an agent indicating execution should be dynamically handed off 
    to a specialized downstream target agent.
    """
    target_agent: str = Field(..., description="Name of target agent to hand off to.")
    reason: str = Field(default="", description="Reason for hand-off.")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Context payload passed to target agent.")
    short_circuit: bool = Field(default=True, description="Whether to bypass central supervisor pipeline.")


class HandOffManager:
    """
    HandOffManager: Enables autonomous Hands-off routing between agents.
    Inspects agent signals or query intents and executes dynamic transfers 
    without relying on fixed supervisor step-by-step dispatching.
    """

    def __init__(self) -> None:
        self._registry: Dict[str, Any] = {}

    def register_agent(self, name: str, agent_instance: Any) -> None:
        """Register an agent instance for dynamic hand-off routing."""
        self._registry[name] = agent_instance
        logger.debug(f"HandOffManager: Registered agent '{name}'")

    def detect_handoff(
        self,
        query: str,
        metadata: Dict[str, Any],
        planner_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[HandOffSignal]:
        """
        Inspects query metadata or planner decision to see if an immediate hand-off is required.
        """
        # 1. Immediate Safety hand-off check
        if metadata.get("safety_triggered", False):
            return HandOffSignal(
                target_agent="SafetyAgent",
                reason="Safety violation detected; short-circuiting to safety response.",
                payload={"query": query, "metadata": metadata},
                short_circuit=True,
            )

        # 2. Gamified Interaction hand-off check
        if metadata.get("game_mode"):
            return HandOffSignal(
                target_agent="ClassroomInteractionAgent",
                reason=f"Game mode requested: {metadata.get('game_mode')}",
                payload={"query": query, "metadata": metadata},
                short_circuit=True,
            )

        # 3. Assessment / Evaluation hand-off check
        action = metadata.get("action")
        if action in ["evaluate", "generate"]:
            return HandOffSignal(
                target_agent="AssessmentAgent",
                reason=f"Assessment action requested: {action}",
                payload={"query": query, "metadata": metadata},
                short_circuit=True,
            )

        # 4. Planner-driven dynamic hand-off
        if planner_data:
            strategy = planner_data.get("teaching_strategy", "")
            execution_plan = planner_data.get("execution_plan", [])

            if "AssessmentAgent" in execution_plan and len(execution_plan) == 1:
                return HandOffSignal(
                    target_agent="AssessmentAgent",
                    reason="Planner routed directly to AssessmentAgent",
                    payload={"query": query, "metadata": metadata},
                    short_circuit=True,
                )
            elif "ContentGenerationAgent" in execution_plan and len(execution_plan) == 1:
                return HandOffSignal(
                    target_agent="ContentGenerationAgent",
                    reason="Planner routed directly to ContentGenerationAgent",
                    payload={"query": query, "metadata": metadata},
                    short_circuit=True,
                )

        return None

    async def execute_handoff(
        self,
        signal: HandOffSignal,
        input_msg: Any,
    ) -> Optional[Any]:
        """Executes hand-off to the target agent if registered."""
        target_name = signal.target_agent
        if target_name not in self._registry:
            logger.error(f"HandOffManager: Target agent '{target_name}' is not registered in HandOffManager.")
            return None

        logger.info(f"HandOffManager: Executing dynamic hand-off to '{target_name}' (Reason: {signal.reason})")
        target_agent = self._registry[target_name]
        start_time = time.perf_counter()

        try:
            reply = await target_agent.reply(input_msg)
            duration = time.perf_counter() - start_time
            logger.info(f"HandOffManager: Hand-off to '{target_name}' completed in {duration:.3f}s")
            return reply
        except Exception as e:
            logger.error(f"HandOffManager: Hand-off execution failed for '{target_name}': {e}")
            raise
