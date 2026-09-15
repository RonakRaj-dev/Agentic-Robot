import os
os.environ["USE_TF"] = "0"
os.environ["USE_TORCH"] = "1"

import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
import asyncio
from services.rate_limiter import RateLimiter
from services.redis_pubsub import RedisPubSubManager
from agents.remote_agent_proxy import RemoteAgentProxy
from agentscope.message import Msg

@pytest.mark.asyncio
async def test_rate_limiter_sliding_window():
    limiter = RateLimiter(max_requests=2, window_seconds=10)
    
    # 1st request - allowed
    allowed, remaining, _ = await limiter.is_allowed("test_ip_1")
    assert allowed is True
    assert remaining == 1
    
    # 2nd request - allowed
    allowed, remaining, _ = await limiter.is_allowed("test_ip_1")
    assert allowed is True
    assert remaining == 0
    
    # 3rd request - rate limited (429)
    allowed, remaining, reset_after = await limiter.is_allowed("test_ip_1")
    assert allowed is False
    assert remaining == 0
    assert reset_after > 0

@pytest.mark.asyncio
async def test_redis_pubsub_fallback():
    pubsub = RedisPubSubManager(redis_url="redis://127.0.0.1:59999/0")
    connected = await pubsub.connect()
    assert connected is False
    assert pubsub.is_connected is False

@pytest.mark.asyncio
async def test_remote_agent_proxy_fallback():
    class DummyAgent:
        async def reply(self, msg):
            return Msg(name="DummyAgent", content="Local fallback reply", role="assistant")

    proxy = RemoteAgentProxy(
        name="ValidationAgent",
        service_url="http://127.0.0.1:59999",
        local_agent_fallback=DummyAgent()
    )
    proxy.agent_mode = "microservice"
    
    res = await proxy.reply(Msg(name="Student", content="Hello"))
    print(f"DEBUG TEST RES: type={type(res)}, res={res}, content={getattr(res, 'content', None)}")
    assert res is not None
    assert "Local fallback reply" in str(res.content) or "Local fallback reply" in str(res)

if __name__ == "__main__":
    async def main():
        await test_rate_limiter_sliding_window()
        await test_redis_pubsub_fallback()
        await test_remote_agent_proxy_fallback()
        print("✅ ALL STATELESS MICROSERVICE TESTS PASSED 100% SUCCESS!")

    asyncio.run(main())

