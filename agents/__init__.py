"""Agents package initialization."""
import models.compat

from .adaptive_learning_agent import AdaptiveLearningAgent
from .analytics_agent import AnalyticsAgent
from .assessment_agent import AssessmentAgent
from .classroom_interaction_agent import ClassroomInteractionAgent
from .content_generation_agent import ContentGenerationAgent
from .memory_agent import MemoryAgent
from .planner_agent import PlannerAgent
from .quiz_agent import QuizAgent
from .response_agent import ResponseAgent
from .safety_agent import SafetyAgent
from .summary_agent import SummaryAgent
from .supervisor_agent import ClassroomSupervisorAgent
from .supervisor_agent_v2 import ClassroomSupervisorAgentV2
from .supervisor_agent_v3 import ClassroomSupervisorAgentV3
from .teaching_agent import TeachingAgent
from .validator_agent import ValidationAgent
from .video_agent import VideoAgent

__all__ = [
    "AdaptiveLearningAgent",
    "AnalyticsAgent",
    "AssessmentAgent",
    "ClassroomInteractionAgent",
    "ContentGenerationAgent",
    "MemoryAgent",
    "PlannerAgent",
    "QuizAgent",
    "ResponseAgent",
    "SafetyAgent",
    "SummaryAgent",
    "ClassroomSupervisorAgent",
    "ClassroomSupervisorAgentV2",
    "ClassroomSupervisorAgentV3",
    "TeachingAgent",
    "ValidationAgent",
    "VideoAgent",
]
