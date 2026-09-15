import sys
import os
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
import asyncio
import time
from fastapi.testclient import TestClient

from services.cache_service import TTLCache, cache_service, cached_endpoint
from models.llm_gateway import LLMGateway, CircuitBreaker, CircuitState
from api.errors import AppBaseException, LLMDegradedError, app_exception_handler
from api.main import app

client = TestClient(app)

def test_cache_service_ttl_and_lru():
    cache = TTLCache(default_ttl_seconds=1, max_size=3)
    cache.set("key1", "val1")
    cache.set("key2", "val2")
    
    assert cache.get("key1") == "val1"
    assert cache.get("key2") == "val2"
    
    # Test expiration
    time.sleep(1.1)
    assert cache.get("key1") is None
    
    # Test LRU eviction
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    cache.set("d", 4)
    assert len(cache._store) <= 3


@pytest.mark.asyncio
async def test_llm_gateway_fallback_mode():
    gateway = LLMGateway()
    # Trigger fallback generation
    res = await gateway.generate("Explain photosynthesis for Class 6 science", max_retries=1)
    assert isinstance(res, str)
    assert len(res) > 0


def test_health_and_readiness_endpoints():
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"

    res_ready = client.get("/readyz")
    assert res_ready.status_code == 200
    assert "status" in res_ready.json()


def test_cached_curriculum_endpoints_latency():
    # First call (cold)
    t0 = time.time()
    res1 = client.get("/api/subjects?class=6")
    t1 = time.time()
    assert res1.status_code == 200
    cold_duration = t1 - t0

    # Second call (warm/cached)
    t2 = time.time()
    res2 = client.get("/api/subjects?class=6")
    t3 = time.time()
    assert res2.status_code == 200
    warm_duration = t3 - t2

    assert res1.json() == res2.json()
    # Cached call should be sub-5ms (< 0.05 seconds)
    assert warm_duration < 0.05


def test_circuit_breaker_transitions():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.2)
    assert cb.state == CircuitState.CLOSED
    assert cb.allow_request() is True

    cb.record_failure()
    assert cb.state == CircuitState.CLOSED

    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.allow_request() is False

    time.sleep(0.3)
    # Should transition to HALF_OPEN
    assert cb.allow_request() is True
    assert cb.state == CircuitState.HALF_OPEN

    cb.record_success()
    assert cb.state == CircuitState.CLOSED
