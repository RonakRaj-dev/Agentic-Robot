"""
Agents Orchestration Module - Silicon Project V3
Provides implementations for Sequential, Concurrent, Group Chat, Hands-off, and Magnetic Attractor multi-agent orchestration.
"""

from .concurrent_executor import ConcurrentExecutor
from .handoff_router import HandOffManager, HandOffSignal
from .group_chat import GroupChatManager
from .magnetic_attractor import MagneticAttractorEngine
from .orchestration_engine import OrchestrationEngine

__all__ = [
    "ConcurrentExecutor",
    "HandOffManager",
    "HandOffSignal",
    "GroupChatManager",
    "MagneticAttractorEngine",
    "OrchestrationEngine",
]
