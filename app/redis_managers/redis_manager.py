"""
Redis manager for caching and rate limiting operations.
"""
from typing import Optional
import redis.asyncio as redis
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class RedisManager:
    """Manager for Redis operations."""
    
    def __init__(self):
        self._client: Optional[redis.Redis] = None
    
    async def get_client(self) -> redis.Redis:
        """Get or create Redis client instance."""
        if self._client is None:
            try:
                self._client = await redis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True
                )
                logger.info("Redis client connected")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise
        return self._client
    
    async def close(self):
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Redis client closed")
    
    async def set(self, key: str, value: str, expire: Optional[int] = None) -> bool:
        """Set a key-value pair in Redis."""
        client = await self.get_client()
        return await client.set(key, value, ex=expire)
    
    async def get(self, key: str) -> Optional[str]:
        """Get a value from Redis."""
        client = await self.get_client()
        return await client.get(key)
    
    async def delete(self, key: str) -> bool:
        """Delete a key from Redis."""
        client = await self.get_client()
        return await client.delete(key)
    
    async def incr(self, key: str) -> int:
        """Increment a key's value."""
        client = await self.get_client()
        return await client.incr(key)
    
    async def setex(self, key: str, time: int, value: str) -> bool:
        """Set a key with expiration time."""
        client = await self.get_client()
        return await client.setex(key, time, value)
    
    async def exists(self, key: str) -> bool:
        """Check if a key exists."""
        client = await self.get_client()
        return await client.exists(key) > 0


# Global Redis manager instance
_redis_manager: Optional[RedisManager] = None


async def get_redis_manager() -> RedisManager:
    """Get the global Redis manager instance."""
    global _redis_manager
    if _redis_manager is None:
        _redis_manager = RedisManager()
    return _redis_manager
