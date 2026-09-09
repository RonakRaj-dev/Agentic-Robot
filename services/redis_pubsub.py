import os
import json
import asyncio
from typing import Callable, Any, Optional, Dict
from loguru import logger
import redis.asyncio as aioredis

class RedisPubSubManager:
    """
    Distributed Redis Pub/Sub manager for multi-replica WebSocket broadcasting
    and stateless cross-node event streaming.
    """
    _instance: Optional['RedisPubSubManager'] = None

    def __new__(cls, *args: Any, **kwargs: Any) -> 'RedisPubSubManager':
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, redis_url: Optional[str] = None) -> None:
        if self._initialized:
            return
        self.redis_url = redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        self.redis_client: Optional[aioredis.Redis] = None
        self.pubsub: Optional[aioredis.client.PubSub] = None
        self.is_connected = False
        self._listeners: Dict[str, list[Callable[[str, dict], Any]]] = {}
        self._listen_task: Optional[asyncio.Task] = None
        self._initialized = True

    async def connect(self) -> bool:
        try:
            self.redis_client = aioredis.from_url(self.redis_url, decode_responses=True)
            await self.redis_client.ping()
            self.is_connected = True
            logger.info(f"Connected to Redis Pub/Sub backplane at: {self.redis_url}")
            return True
        except Exception as e:
            logger.warning(f"Redis Pub/Sub unavailable ({e}). Operating in single-node mode.")
            self.is_connected = False
            return False

    async def publish(self, channel: str, message: dict) -> bool:
        if not self.is_connected or not self.redis_client:
            return False
        try:
            payload = json.dumps(message)
            await self.redis_client.publish(channel, payload)
            return True
        except Exception as e:
            logger.error(f"Error publishing to Redis channel '{channel}': {e}")
            return False

    async def subscribe(self, channel: str, callback: Callable[[str, dict], Any]) -> None:
        if channel not in self._listeners:
            self._listeners[channel] = []
        self._listeners[channel].append(callback)

        if self.is_connected and self.redis_client and not self.pubsub:
            try:
                self.pubsub = self.redis_client.pubsub()
                await self.pubsub.subscribe(channel)
                if not self._listen_task or self._listen_task.done():
                    self._listen_task = asyncio.create_task(self._listen_loop())
            except Exception as e:
                logger.error(f"Error subscribing to Redis channel '{channel}': {e}")

    async def _listen_loop(self) -> None:
        if not self.pubsub:
            return
        try:
            async for message in self.pubsub.listen():
                if message.get("type") == "message":
                    channel = message.get("channel")
                    data_str = message.get("data")
                    try:
                        data = json.loads(data_str)
                        callbacks = self._listeners.get(channel, [])
                        for cb in callbacks:
                            if asyncio.iscoroutinefunction(cb):
                                await cb(channel, data)
                            else:
                                cb(channel, data)
                    except Exception as err:
                        logger.error(f"Error handling Redis Pub/Sub payload on {channel}: {err}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Redis Pub/Sub listener loop exception: {e}")

    async def close(self) -> None:
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
        if self.pubsub:
            await self.pubsub.unsubscribe()
            await self.pubsub.close()
        if self.redis_client:
            await self.redis_client.close()
        self.is_connected = False
        logger.info("Redis Pub/Sub manager closed.")

redis_pubsub = RedisPubSubManager()
