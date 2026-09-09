import time
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger
from agentscope.message import UserMsg, AssistantMsg
from models.schemas import AgentResult, get_content_str

from .concurrent_executor import ConcurrentExecutor
from .handoff_router import HandOffManager, HandOffSignal
from .group_chat import GroupChatManager
from .magnetic_attractor import MagneticAttractorEngine


class OrchestrationEngine:
    """
    OrchestrationEngine: Unified multi-agent orchestration hub for Silicon Project V3.
    Integrates all 5 agentic orchestration patterns:
    1. Sequential (Chain guardrails & egress formatting)
    2. Concurrent (Fan-out parallel pre-fetch & post-asset generation)
    3. Group Chat (Round-table debate between Teaching & Adaptive agents)
    4. Hands-off (Dynamic hand-off routing to specialized target agents)
    5. Magnetic Attractor (Iterative factual groundedness convergence loop)
    """

    def __init__(self, agent_registry: Dict[str, Any]) -> None:
        self.registry = agent_registry
        self.concurrent_executor = ConcurrentExecutor()
        self.handoff_manager = HandOffManager()
        
        # Register agents in HandOffManager
        for name, instance in agent_registry.items():
            self.handoff_manager.register_agent(name, instance)

        # Instantiate Group Chat Manager
        self.group_chat_manager = GroupChatManager(
            teaching_agent=agent_registry.get("teaching_agent"),
            adaptive_agent=agent_registry.get("adaptive_agent"),
            assessment_agent=agent_registry.get("assessment_agent"),
        )

        # Instantiate Magnetic Attractor Engine
        self.magnetic_attractor_engine = MagneticAttractorEngine(
            teaching_agent=agent_registry.get("teaching_agent"),
            verification_agent=agent_registry.get("verification_agent"),
            target_groundedness=0.85,
            max_attractor_attempts=2,
        )

    async def execute_sequential_guardrails(
        self,
        query: str,
        pipeline_metadata: Dict[str, Any],
    ) -> Tuple[bool, Optional[AssistantMsg]]:
        """
        Pattern 1: Sequential Execution (ValidationAgent -> SafetyAgent)
        Returns (is_safe, failure_msg).
        """
        val_agent = self.registry.get("validation_agent")
        safety_agent = self.registry.get("safety_agent")

        # Step 1: Validation
        val_msg = UserMsg(name="Supervisor", content=query, metadata=pipeline_metadata)
        val_reply = await val_agent.reply(val_msg)
        val_res_dict = getattr(val_reply, "metadata", {}).get("agent_result", {})
        if not val_res_dict.get("success", False):
            return False, val_reply

        # Step 2: Safety
        safety_msg = UserMsg(name="Supervisor", content=query, metadata=pipeline_metadata)
        safety_reply = await safety_agent.reply(safety_msg)
        safety_res_dict = getattr(safety_reply, "metadata", {}).get("agent_result", {})
        if not safety_res_dict.get("success", False):
            return False, safety_reply

        return True, None

    async def execute_concurrent_prefetch(
        self,
        query: str,
        pipeline_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Pattern 2: Concurrent Execution (MemoryAgent, AdaptiveLearningAgent, PlannerAgent)
        """
        mem_agent = self.registry.get("memory_agent")
        adaptive_agent = self.registry.get("adaptive_agent")
        planner_agent = self.registry.get("planner_agent")

        mem_msg = UserMsg(name="Supervisor", content=query, metadata=pipeline_metadata)
        adaptive_msg = UserMsg(name="Supervisor", content=query, metadata=pipeline_metadata)
        planner_msg = UserMsg(name="Supervisor", content=query, metadata=pipeline_metadata)

        tasks = {
            "memory": mem_agent.reply(mem_msg),
            "adaptive": adaptive_agent.reply(adaptive_msg),
            "planner": planner_agent.reply(planner_msg),
        }

        return await self.concurrent_executor.execute_parallel(tasks)

    async def execute_concurrent_asset_generation(
        self,
        query: str,
        final_answer: str,
        plan_data: Dict[str, Any],
        pipeline_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Pattern 2: Concurrent Execution for post-explanation asset enrichment
        (VideoAgent, QuizAgent, SummaryAgent)
        """
        tasks = {}
        if plan_data.get("need_video") or "VideoAgent" in plan_data.get("execution_plan", []):
            video_agent = self.registry.get("video_agent")
            tasks["video"] = video_agent.reply(UserMsg(name="Supervisor", content=query, metadata=pipeline_metadata))

        if plan_data.get("need_quiz") or "QuizAgent" in plan_data.get("execution_plan", []):
            quiz_agent = self.registry.get("quiz_agent")
            tasks["quiz"] = quiz_agent.reply(UserMsg(name="Supervisor", content=query, metadata=pipeline_metadata))

        if plan_data.get("need_summary") or "SummaryAgent" in plan_data.get("execution_plan", []):
            summary_agent = self.registry.get("summary_agent")
            tasks["summary"] = summary_agent.reply(UserMsg(name="Supervisor", content=final_answer, metadata=pipeline_metadata))

        if not tasks:
            return {}

        return await self.concurrent_executor.execute_parallel(tasks)

    def check_hands_off_routing(
        self,
        query: str,
        pipeline_metadata: Dict[str, Any],
        planner_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[HandOffSignal]:
        """
        Pattern 4: Hands-off Orchestration Check
        """
        return self.handoff_manager.detect_handoff(query, pipeline_metadata, planner_data)

    async def execute_group_chat_dialogue(
        self,
        query: str,
        context_str: str,
        adaptive_data: Dict[str, Any],
        pipeline_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Pattern 3: Group Chat Orchestration Dialogue
        """
        return await self.group_chat_manager.run_lesson_refinement_chat(
            query=query,
            context_str=context_str,
            adaptive_data=adaptive_data,
            pipeline_metadata=pipeline_metadata,
        )

    async def execute_magnetic_attractor_convergence(
        self,
        initial_explanation: str,
        retrieved_chunks: List[Dict[str, Any]],
        grounded_query: str,
        pipeline_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Pattern 5: Magnetic Attractor Orchestration Convergence
        """
        return await self.magnetic_attractor_engine.converge_explanation_attractor(
            initial_explanation=initial_explanation,
            retrieved_chunks=retrieved_chunks,
            grounded_query=grounded_query,
            pipeline_metadata=pipeline_metadata,
        )
