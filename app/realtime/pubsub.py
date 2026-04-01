"""
Redis Pub/Sub Manager for cross-server WebSocket broadcasting.
"""
import asyncio
import json
import logging
from typing import Optional, Callable, Dict
import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisPubSubManager:
    """
    Manages Redis Pub/Sub for distributing WebSocket messages across multiple server instances.
    """

    def __init__(self):
        self._redis_client: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
        self._subscriber_task: Optional[asyncio.Task] = None
        self._message_handlers: Dict[str, Callable] = {}
        self._running = False

    async def connect(self):
        """Initialize Redis connection for Pub/Sub."""
        try:
            logger.info("Initializing Redis Pub/Sub connection...")
            self._redis_client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self._redis_client.ping()
            logger.info("Redis Pub/Sub connection established")
        except Exception as e:
            logger.error(f"Failed to connect to Redis for Pub/Sub: {e}")
            raise

    async def disconnect(self):
        """Close Redis Pub/Sub connection."""
        self._running = False
        
        if self._subscriber_task:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass
        
        if self._pubsub:
            await self._pubsub.close()
        
        if self._redis_client:
            await self._redis_client.close()
        
        logger.info("Redis Pub/Sub connection closed")

    async def publish(self, channel: str, message: dict):
        """
        Publish a message to a Redis channel.
        
        Args:
            channel: Redis channel name (e.g., "group:123")
            message: Message dictionary to publish
        """
        if not self._redis_client:
            logger.warning("Redis client not initialized, skipping publish")
            return
        
        try:
            message_json = json.dumps(message)
            await self._redis_client.publish(channel, message_json)
            logger.debug(f"Published message to channel {channel}")
        except Exception as e:
            logger.error(f"Failed to publish to Redis channel {channel}: {e}")

    def register_handler(self, pattern: str, handler: Callable):
        """
        Register a message handler for a channel pattern.
        
        Args:
            pattern: Channel pattern (e.g., "group:*")
            handler: Async function to handle messages: async def handler(channel, message)
        """
        self._message_handlers[pattern] = handler
        logger.info(f"Registered handler for pattern: {pattern}")

    async def start_subscriber(self):
        """Start the background subscriber task."""
        if not self._redis_client:
            await self.connect()
        
        self._pubsub = self._redis_client.pubsub()
        
        # Subscribe to all registered patterns
        for pattern in self._message_handlers.keys():
            await self._pubsub.psubscribe(pattern)
            logger.info(f"Subscribed to pattern: {pattern}")
        
        self._running = True
        self._subscriber_task = asyncio.create_task(self._listen())
        logger.info("Redis Pub/Sub subscriber started")

    async def _listen(self):
        """Background task that listens for Redis Pub/Sub messages."""
        try:
            while self._running:
                try:
                    message = await self._pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=settings.REDIS_PUBSUB_TIMEOUT
                    )
                    
                    if message and message["type"] == "pmessage":
                        await self._handle_message(message)
                
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in Pub/Sub listener: {e}")
                    await asyncio.sleep(1)  # Brief pause before retry
        
        except asyncio.CancelledError:
            logger.info("Pub/Sub listener cancelled")
        finally:
            logger.info("Pub/Sub listener stopped")

    async def _handle_message(self, message: dict):
        """
        Handle an incoming Pub/Sub message.
        
        Args:
            message: Redis Pub/Sub message dict with keys: pattern, channel, data
        """
        try:
            pattern = message["pattern"]
            channel = message["channel"]
            data = json.loads(message["data"])
            
            handler = self._message_handlers.get(pattern)
            if handler:
                await handler(channel, data)
            else:
                logger.warning(f"No handler for pattern {pattern}")
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode Pub/Sub message: {e}")
        except Exception as e:
            logger.error(f"Error handling Pub/Sub message: {e}")


# Global Pub/Sub manager instance
pubsub_manager = RedisPubSubManager()
