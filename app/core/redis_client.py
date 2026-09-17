import os
import redis.asyncio as redis

class RedisClient:
    def __init__(self):
        redis_url = os.getenv("REDIS_URL")
        
        if redis_url:
            # Connect via full URL (handles Upstash tls/rediss:// and auth automatically)
            self.client = redis.from_url(redis_url, decode_responses=False)
        else:
            # Fallback for local development
            self.client = redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                password=os.getenv("REDIS_PASSWORD", None),
                decode_responses=False # Keep binary format for vector bytes
            )

    async def ping(self) -> bool:
        return await self.client.ping()

# Instantiate the service once globally
redis_service = RedisClient()