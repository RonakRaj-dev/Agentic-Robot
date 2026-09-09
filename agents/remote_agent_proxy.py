import os
import asyncio
import httpx
from typing import Any, Optional, Dict
from loguru import logger
from agentscope.agent import Agent
from agentscope.message import Msg

class RemoteAgentProxy(Agent):
    """
    Stateless Remote Agent Proxy.
    Forward reply requests to an isolated microservice container over HTTP RPC
    when AGENT_MODE=microservice, providing 100% stateless execution.
    """
    def __init__(
        self,
        name: str,
        service_url: str,
        local_agent_fallback: Optional[Agent] = None,
        **kwargs: Any
    ) -> None:
        super().__init__()
        self.name = name
        self.service_url = service_url
        self.local_agent_fallback = local_agent_fallback
        self.agent_mode = os.environ.get("AGENT_MODE", "monolith").lower()

    async def reply(self, x: Any = None) -> Msg:
        # Check if running in microservice mode
        if self.agent_mode == "microservice" or os.environ.get(f"{self.name.upper()}_URL"):
            url = os.environ.get(f"{self.name.upper()}_URL") or self.service_url
            try:
                msg_dict = {}
                if isinstance(x, Msg):
                    msg_dict = {
                        "name": x.name,
                        "content": str(x.content),
                        "role": getattr(x, "role", "user"),
                        "metadata": getattr(x, "metadata", {}) or {}
                    }
                elif isinstance(x, dict):
                    msg_dict = x
                else:
                    msg_dict = {"name": "User", "content": str(x), "metadata": {}}

                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(f"{url}/reply", json=msg_dict)
                    if resp.status_code == 200:
                        data = resp.json()
                        return Msg(
                            name=data.get("name", self.name),
                            content=data.get("content", ""),
                            role=data.get("role", "assistant"),
                            metadata=data.get("metadata", {})
                        )
                    else:
                        logger.warning(f"Remote microservice {self.name} at {url} returned HTTP {resp.status_code}. Falling back.")
            except Exception as e:
                logger.warning(f"Failed to communicate with remote microservice {self.name} at {url}: {e}. Falling back.")

        # Fallback to local in-process agent execution
        if self.local_agent_fallback:
            if asyncio.iscoroutinefunction(self.local_agent_fallback.reply):
                return await self.local_agent_fallback.reply(x)
            res = self.local_agent_fallback.reply(x)
            if asyncio.iscoroutine(res):
                return await res
            return res

        raise RuntimeError(f"Microservice agent '{self.name}' unavailable and no local fallback supplied.")
