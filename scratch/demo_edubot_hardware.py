import models.compat
import asyncio
import time
from loguru import logger

from services.ros2_bridge import ros2_bridge
from services.idle_expression_service import idle_expression_service
from models.schemas import TeachingResponse
from agentscope.message import Msg
from agents.supervisor_agent_v3 import ClassroomSupervisorAgentV3

async def run_edubot_demo():
    logger.info("="*70)
    logger.info("🤖 EDU-BOT HARDWARE & SOFTWARE INTEGRATION DEMO")
    logger.info("="*70)
    
    # 1. Start Idle Expression Engine
    logger.info("Step 1: Starting Idle Expression Engine background loop...")
    await idle_expression_service.start()
    await asyncio.sleep(1.0)

    # 2. Simulate Active Query Processing
    logger.info("--- [Active Interaction Phase] ---")
    logger.info("Simulating incoming student query: 'How do plants make food?'")
    idle_expression_service.record_activity()
    
    # RAG calculation phase -> publish THINKING
    ros2_bridge.publish_expression("EXPRESSION_THINKING")
    await asyncio.sleep(0.5)

    # Execute Supervisor Agent V3 query
    supervisor = ClassroomSupervisorAgentV3(name="SupervisorV3")
    msg = Msg(
        name="Student",
        content="How do plants make food?",
        metadata={"session_id": "demo_session", "grade": 6, "subject": "Science"}
    )
    
    logger.info("Executing ClassroomSupervisorAgentV3 pipeline...")
    reply = await supervisor.reply(msg)
    
    agent_result = getattr(reply, "metadata", {}).get("agent_result", {})
    res_data = agent_result.get("data") if isinstance(agent_result.get("data"), dict) else {}
    
    logger.info("--- [Agent Delivery Payload] ---")
    logger.info(f"Success: {agent_result.get('success')}")
    logger.info(f"Expression Tag: {res_data.get('expression', 'EXPRESSION_NOD')}")
    logger.info(f"Answer Summary: {res_data.get('summary', agent_result.get('error', 'No summary available'))}")
    
    # Publish active speech expression
    delivered_expr = res_data.get("expression", "EXPRESSION_TALKING")
    ros2_bridge.publish_expression(delivered_expr)

    # 3. Simulate Idle Period (>3 seconds) to demonstrate Involuntary Expressions
    logger.info("--- [Passive Idle Action Phase] ---")
    logger.info("Simulating 7 seconds of idle student silence to trigger passive eye blinks & look-around...")
    await asyncio.sleep(7.5)

    # 4. Stop Services
    logger.info("--- [Shutdown Phase] ---")
    logger.info("Stopping Idle Expression Service...")
    await idle_expression_service.stop()
    logger.info("✅ EDU-BOT DEMO COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(run_edubot_demo())
