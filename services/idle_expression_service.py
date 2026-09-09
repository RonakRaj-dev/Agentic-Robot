import asyncio
import time
import random
from typing import Optional
from loguru import logger
from services.ros2_bridge import ros2_bridge

class IdleExpressionService:
    """
    Involuntary Idle Expression Engine for Edu-Bot hardware.
    Monitors user activity timestamps and periodically publishes passive
    expression messages (EXPRESSION_BLINK, EXPRESSION_LONG_BLINK, EXPRESSION_LOOK_AROUND)
    over ROS2 whenever student interaction is idle (>3.0 seconds).
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(IdleExpressionService, cls).__new__(cls, *args, **kwargs)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, idle_threshold: float = 3.0, poll_interval: float = 2.5) -> None:
        if self._initialized:
            return
        
        self.idle_threshold = idle_threshold
        self.poll_interval = poll_interval
        self.last_activity_time: float = time.time()
        self.is_running: bool = False
        self._task: Optional[asyncio.Task] = None
        self._initialized = True

    def record_activity(self) -> None:
        """Call this whenever an active query or user interaction occurs to reset idle timer."""
        self.last_activity_time = time.time()

    async def start(self) -> None:
        if self.is_running:
            return
        
        self.is_running = True
        self.last_activity_time = time.time()
        self._task = asyncio.create_task(self._idle_loop())
        logger.info("IdleExpressionService started background passive expression loop.")

    async def stop(self) -> None:
        if not self.is_running:
            return
        
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("IdleExpressionService stopped.")

    async def _idle_loop(self) -> None:
        passive_expressions = [
            "EXPRESSION_BLINK",
            "EXPRESSION_BLINK",
            "EXPRESSION_LONG_BLINK",
            "EXPRESSION_LOOK_AROUND"
        ]

        while self.is_running:
            await asyncio.sleep(self.poll_interval)
            now = time.time()
            time_since_activity = now - self.last_activity_time

            if time_since_activity >= self.idle_threshold:
                chosen_exp = random.choice(passive_expressions)
                logger.debug(f"Idle detected ({round(time_since_activity, 1)}s idle). Triggering passive expression: {chosen_exp}")
                ros2_bridge.publish_expression(chosen_exp)


# Global Singleton
idle_expression_service = IdleExpressionService()
