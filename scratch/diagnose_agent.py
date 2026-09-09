import sys
import os
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import asyncio
from agentscope.message import Msg
# Corrected import below in run()

async def run():
    # Let's import the ClassroomSupervisorAgentV3
    from agents.supervisor_agent_v3 import ClassroomSupervisorAgentV3
    
    agent = ClassroomSupervisorAgentV3(name="SupervisorV3")
    
    msg = Msg(
        name="Student",
        content="What this chapter about ?",
        metadata={
            "session_id": "test_sess_diagnose",
            "grade": 9,
            "subject": "Science",
            "chapter": "Chapter 2: Iesc102",
            "student_id": "test_student"
        }
    )
    
    try:
        reply = await agent.reply(msg)
        print("Reply received successfully:")
        print(reply.content)
    except Exception as e:
        import traceback
        print("Agent execution threw an exception:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run())
