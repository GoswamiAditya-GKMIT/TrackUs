import logging
from typing import Optional
import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)

# Global Redis client instance
_redis_client: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    """
    Get or create Redis client instance.
    Returns the global Redis client for dependency injection.
    """
    global _redis_client
    
    if _redis_client is None:
        raise RuntimeError("Redis client not initialized. Call init_redis() first.")
    
    return _redis_client


async def init_redis() -> None:
    """
    Initialize Redis connection on application startup.
    """
    global _redis_client
    
    try:
        logger.info(f"Connecting to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}...")
        
        _redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        
        # Test connection
        await _redis_client.ping()
        
        logger.info("Redis connection established successfully")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {str(e)}")
        raise


async def close_redis() -> None:
    """
    Close Redis connection on application shutdown.
    """
    global _redis_client
    
    if _redis_client:
        logger.info("Closing Redis connection...")
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis connection closed")
