import redis.asyncio as redis
from config.settings import settings

redis_client = None


async def get_redis():
    """Initialize Redis connection."""
    global redis_client
    if redis_client is None:
        redis_client = await redis.from_url(settings.redis_url)
    return redis_client


async def close_redis():
    """Close Redis connection."""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None
