import os
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
from agentscope.message import Msg
from agents.quiz_agent.agents.agent import QuizAgent

app = FastAPI(title="Quiz Agent Microservice", version="3.0.0")
agent = QuizAgent(name="QuizAgent")

class AgentMsgRequest(BaseModel):
    name: str = "Student"
    content: str
    role: Optional[str] = "user"
    metadata: Optional[Dict[str, Any]] = None

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "QuizAgent", "port": 8004}

@app.post("/reply")
async def reply(req: AgentMsgRequest):
    try:
        msg = Msg(name=req.name, content=req.content, role=req.role, metadata=req.metadata or {})
        res = await agent.reply(msg)
        return {
            "name": res.name,
            "content": str(res.content),
            "role": getattr(res, "role", "assistant"),
            "metadata": getattr(res, "metadata", {}) or {}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
