import time
import asyncio
from typing import Any, Dict, Optional, Tuple, Callable
from functools import wraps
from loguru import logger

import os
import json
import redis.asyncio as aioredis

class TTLCache:
    """
    High-performance in-memory TTL & LRU cache with optional Redis backend connection.
    Reduces latency for repetitive curriculum & metadata database queries.
    """
    def __init__(self, default_ttl_seconds: int = 300, max_size: int = 1000) -> None:
        self.default_ttl = default_ttl_seconds
        self.max_size = max_size
        self._store: Dict[str, Tuple[Any, float]] = {}
        self._lock = asyncio.Lock()
        self.redis_client: Optional[aioredis.Redis] = None
        self.is_connected = False

    async def connect(self, redis_url: Optional[str] = None) -> bool:
        url = redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        try:
            self.redis_client = aioredis.from_url(url, decode_responses=True)
            await self.redis_client.ping()
            self.is_connected = True
            logger.info(f"Connected to Redis cache at: {url}")
            return True
        except Exception:
            self.is_connected = False
            self.redis_client = None
            return False

    async def close(self) -> None:
        if self.redis_client:
            await self.redis_client.close()
        self.is_connected = False

    def get(self, key: str) -> Optional[Any]:
        if key not in self._store:
            return None
        val, expiry = self._store[key]
        if time.time() > expiry:
            del self._store[key]
            return None
        return val

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        if len(self._store) >= self.max_size:
            # Evict oldest 10% of entries if at capacity
            keys_to_remove = list(self._store.keys())[: max(1, self.max_size // 10)]
            for k in keys_to_remove:
                self._store.pop(k, None)

        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        expiry = time.time() + ttl
        self._store[key] = (value, expiry)

    def clear(self) -> None:
        self._store.clear()


# Global cache instance for API responses
cache_service = TTLCache(default_ttl_seconds=300, max_size=2000)


def cached_endpoint(ttl_seconds: int = 300):
    """Decorator for caching async FastAPI endpoint responses based on function arguments."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Exclude FastAPI Request object from cache key if present
            filtered_kwargs = {k: v for k, v in kwargs.items() if not hasattr(v, "scope")}
            key = f"{func.__name__}:{args}:{sorted(filtered_kwargs.items())}"
            
            cached_res = cache_service.get(key)
            if cached_res is not None:
                return cached_res
            
            res = await func(*args, **kwargs)
            if res:
                cache_service.set(key, res, ttl_seconds=ttl_seconds)
            return res
        return wrapper
    return decorator
