import time
import asyncio
from typing import Optional, Dict, Tuple
from loguru import logger
from fastapi import Request, HTTPException, status
from services.cache_service import cache_service

class RateLimiter:
    """
    Sliding-window Rate Limiter using Redis (if available) or in-memory fallback
    to prevent API quota drain, DDoS attacks, and resource abuse.
    """
    def __init__(self, max_requests: int = 60, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._memory_store: Dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def is_allowed(self, identifier: str) -> Tuple[bool, int, float]:
        """
        Checks if the given identifier (IP/Student ID) is within rate limits.
        Returns: (allowed: bool, remaining_requests: int, reset_after_seconds: float)
        """
        now = time.time()
        window_start = now - self.window_seconds
        cache_key = f"rate_limit:{identifier}"

        # 1. Try Redis sliding-window check if connected
        if cache_service.is_connected and cache_service.redis_client:
            try:
                pipe = cache_service.redis_client.pipeline()
                pipe.zremrangebyscore(cache_key, 0, window_start)
                pipe.zcard(cache_key)
                pipe.zadd(cache_key, {str(now): now})
                pipe.expire(cache_key, self.window_seconds)
                results = await pipe.execute()

                current_count = results[1]
                if current_count >= self.max_requests:
                    # Remove the just-added request to keep accurate count
                    await cache_service.redis_client.zrem(cache_key, str(now))
                    return False, 0, float(self.window_seconds)
                
                remaining = max(0, self.max_requests - (current_count + 1))
                return True, remaining, float(self.window_seconds)
            except Exception as e:
                logger.warning(f"Redis rate limiter exception ({e}). Falling back to memory store.")

        # 2. In-Memory Sliding Window Fallback
        async with self._lock:
            timestamps = self._memory_store.get(identifier, [])
            valid_timestamps = [t for t in timestamps if t > window_start]
            
            if len(valid_timestamps) >= self.max_requests:
                self._memory_store[identifier] = valid_timestamps
                oldest = valid_timestamps[0]
                reset_after = max(0.1, round((oldest + self.window_seconds) - now, 1))
                return False, 0, reset_after

            valid_timestamps.append(now)
            self._memory_store[identifier] = valid_timestamps
            remaining = self.max_requests - len(valid_timestamps)
            return True, remaining, float(self.window_seconds)

rate_limiter = RateLimiter(max_requests=60, window_seconds=60)

async def check_rate_limit(request: Request, student_id: Optional[str] = None):
    """FastAPI dependency or decorator helper to enforce rate limiting."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    identifier = student_id or request.headers.get("x-institute-id") or client_ip

    allowed, remaining, reset_after = await rate_limiter.is_allowed(identifier)
    if not allowed:
        logger.warning(f"Rate limit exceeded for identifier: {identifier}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded. Too many requests.",
                "reset_after_seconds": reset_after,
                "max_requests_per_minute": rate_limiter.max_requests
            },
            headers={"Retry-After": str(int(reset_after))}
        )
