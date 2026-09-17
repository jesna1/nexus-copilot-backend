import redis.asyncio as redis
from app.core.config import settings

class RedisClient:
    def __init__(self):
        self.client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=False # Keep binary format for vector bytes
        )

    async def ping(self) -> bool:
        return await self.client.ping()

redis_service = RedisClient()