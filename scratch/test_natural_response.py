import os
import sys
import asyncio
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath("."))
load_dotenv()

from agents.supervisor_agent_v3 import ClassroomSupervisorAgentV3
from agentscope.message import Msg

async def main():
    sup = ClassroomSupervisorAgentV3()
    query = "What happens to a plastic bottle when it is empty and when it is completely filled with water?"
    msg = Msg(
        name="Student",
        content=query,
        metadata={
            "session_id": "test_natural_sess",
            "grade": 5,
            "subject": "Science",
            "student_id": "test_student"
        }
    )
    print(f"Running query: '{query}' for Class 5 Science...")
    reply = await sup.reply(msg)
    data = getattr(reply, "metadata", {}).get("agent_result", {}).get("data", {})
    
    print("\n" + "=" * 60)
    print("NATURAL GENERATED RESPONSE FOR STUDENT:")
    print("=" * 60)
    print(data.get("answer"))
    print("=" * 60)
    print(f"Summary: {data.get('summary')}")
    print(f"Key Points: {data.get('key_points')}")
    print(f"Confidence: {data.get('confidence_score')}")

if __name__ == "__main__":
    asyncio.run(main())
