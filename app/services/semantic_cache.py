import struct
import numpy as np
from app.core.redis_client import redis_service
from app.core.gemini_client import gemini_service

INDEX_NAME = "idx:semantic_cache"
PREFIX = "cache:"
VECTOR_DIM = 768

class SemanticCacheService:
    def __init__(self):
        self.redis = redis_service.client

    async def init_index(self):
        """Creates the RediSearch vector index if it does not exist."""
        try:
            await self.redis.execute_command(
                "FT.CREATE", INDEX_NAME,
                "ON", "HASH",
                "PREFIX", "1", PREFIX,
                "SCHEMA",
                "prompt", "TEXT",
                "response", "TEXT",
                "embedding", "VECTOR", "FLAT", "6",
                "TYPE", "FLOAT32",
                "DIM", str(VECTOR_DIM),
                "DISTANCE_METRIC", "COSINE"
            )
            print("RediSearch Semantic Index created successfully.")
        except Exception as e:
            if "Index already exists" in str(e):
                pass
            else:
                print(f"Index initialization error: {e}")

    async def search(self, query_embedding: list[float], threshold: float = 0.92):
        """Searches Redis for semantically similar prompts above the threshold."""
        # Convert embedding float array to raw bytes
        query_bytes = np.array(query_embedding, dtype=np.float32).tobytes()
        
        # Query RediSearch for top 1 nearest vector
        query = f"*=>[KNN 1 @embedding $vec AS vector_score]"
        
        try:
            res = await self.redis.execute_command(
                "FT.SEARCH", INDEX_NAME, query,
                "PARAMS", "2", "vec", query_bytes,
                "RETURN", "2", "response", "vector_score",
                "DIALECT", "2"
            )

            if res and res[0] > 0:
                # Parse RediSearch returned array
                doc_fields = res[2]
                field_dict = {
                    doc_fields[i].decode('utf-8'): doc_fields[i+1].decode('utf-8')
                    for i in range(0, len(doc_fields), 2)
                }
                
                # RediSearch COSINE distance range is 0 (exact match) to 2 (opposite)
                cosine_distance = float(field_dict.get("vector_score", 1.0))
                similarity = 1.0 - cosine_distance

                if similarity >= threshold:
                    return field_dict.get("response"), similarity

        except Exception as e:
            print(f"Semantic Cache Search Error: {e}")

        return None, 0.0

    async def store(self, key_id: str, prompt: str, response: str, query_embedding: list[float]):
        """Stores prompt, response, and binary vector embedding in Redis."""
        query_bytes = np.array(query_embedding, dtype=np.float32).tobytes()
        redis_key = f"{PREFIX}{key_id}"

        await self.redis.hset(
            redis_key,
            mapping={
                "prompt": prompt,
                "response": response,
                "embedding": query_bytes
            }
        )

semantic_cache = SemanticCacheService()