import json
import logging
from typing import Optional, Dict, List
import redis.asyncio as redis
from datetime import datetime

logger = logging.getLogger(__name__)


class MemoryManager:
    def __init__(self):
        """Initialize memory manager."""
        self.redis_client = None

    async def _get_redis(self):
        """Get Redis client."""
        if self.redis_client is None:
            from config.redis_config import get_redis
            self.redis_client = await get_redis()
        return self.redis_client

    async def store_conversation(
        self, session_id: str, messages: List[Dict], ttl: int = 86400
    ):
        """Store conversation history in Redis."""
        try:
            redis = await self._get_redis()
            key = f"conversation:{session_id}"
            await redis.set(
                key,
                json.dumps({"messages": messages, "timestamp": datetime.utcnow().isoformat()}),
                ex=ttl,
            )
            logger.info(f"Stored conversation for session {session_id}")
        except Exception as e:
            logger.error(f"Error storing conversation: {e}")

    async def retrieve_conversation(self, session_id: str) -> Optional[List[Dict]]:
        """Retrieve conversation history from Redis."""
        try:
            redis = await self._get_redis()
            key = f"conversation:{session_id}"
            data = await redis.get(key)

            if data:
                return json.loads(data).get("messages", [])
            return []

        except Exception as e:
            logger.error(f"Error retrieving conversation: {e}")
            return []

    async def store_patient_context(
        self, phone_number: str, context: Dict, ttl: int = 604800
    ):
        """Store patient context in Redis."""
        try:
            redis = await self._get_redis()
            key = f"patient_context:{phone_number}"
            await redis.set(
                key,
                json.dumps({**context, "updated_at": datetime.utcnow().isoformat()}),
                ex=ttl,
            )
            logger.info(f"Stored context for patient {phone_number}")
        except Exception as e:
            logger.error(f"Error storing patient context: {e}")

    async def retrieve_patient_context(self, phone_number: str) -> Optional[Dict]:
        """Retrieve patient context from Redis."""
        try:
            redis = await self._get_redis()
            key = f"patient_context:{phone_number}"
            data = await redis.get(key)

            if data:
                return json.loads(data)
            return None

        except Exception as e:
            logger.error(f"Error retrieving patient context: {e}")
            return None

    async def cache_appointment(self, appointment_id: int, appointment: Dict, ttl: int = 3600):
        """Cache appointment in Redis."""
        try:
            redis = await self._get_redis()
            key = f"appointment:{appointment_id}"
            await redis.set(
                key,
                json.dumps(appointment),
                ex=ttl,
            )
            logger.info(f"Cached appointment {appointment_id}")
        except Exception as e:
            logger.error(f"Error caching appointment: {e}")

    async def get_cached_appointment(self, appointment_id: int) -> Optional[Dict]:
        """Get cached appointment from Redis."""
        try:
            redis = await self._get_redis()
            key = f"appointment:{appointment_id}"
            data = await redis.get(key)

            if data:
                return json.loads(data)
            return None

        except Exception as e:
            logger.error(f"Error getting cached appointment: {e}")
            return None

    async def delete_cache(self, key: str):
        """Delete cache entry."""
        try:
            redis = await self._get_redis()
            await redis.delete(key)
            logger.info(f"Deleted cache key: {key}")
        except Exception as e:
            logger.error(f"Error deleting cache: {e}")
