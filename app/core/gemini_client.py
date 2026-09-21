import os
import itertools
from typing import AsyncGenerator
from google import genai
from google.genai import errors
from app.core.config import settings


class GeminiClientPool:
    def __init__(self):
        # Load keys from settings or environment
        raw_keys = getattr(settings, "GEMINI_API_KEYS", "") or os.getenv("GEMINI_API_KEYS", "")

        # Fallback to single GEMINI_API_KEY if key pool isn't configured
        if not raw_keys and hasattr(settings, "GEMINI_API_KEY"):
            raw_keys = settings.GEMINI_API_KEY

        self.api_keys = [k.strip() for k in raw_keys.split(",") if k.strip()]

        if not self.api_keys:
            raise ValueError("No Gemini API keys configured in environment.")

        # Infinite round-robin iterator across provided keys
        self._key_cycle = itertools.cycle(self.api_keys)

    def _get_next_client(self) -> genai.Client:
        """Fetch a genai.Client initialized with the next key in rotation."""
        key = next(self._key_cycle)
        return genai.Client(api_key=key)

    async def get_embedding(self, text: str) -> list[float]:
        """Generate text embedding with automatic 429 key failover."""
        attempts = len(self.api_keys)

        for attempt in range(attempts):
            client = self._get_next_client()
            try:
                # Async embedding via client.aio
                response = await client.aio.models.embed_content(
                    model="text-embedding-004",
                    contents=text,
                )
                if hasattr(response, "embedding") and response.embedding:
                    return response.embedding.values
                elif hasattr(response, "embeddings") and response.embeddings:
                    return response.embeddings[0].values
                raise ValueError("No embedding vector returned in response.")

            except errors.APIError as e:
                if e.code == 429 or "RESOURCE_EXHAUSTED" in str(e):
                    print(
                        f"[Gemini Key Failover] 429 on embedding (Attempt {attempt+1}/{attempts}). Rotating key..."
                    )
                    continue
                raise e
            except Exception as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    continue
                raise e

        raise Exception("All configured Gemini API keys exceeded quota (429 Rate Limit).")

    async def stream_response(self, prompt: str) -> AsyncGenerator[str, None]:
        """Stream response chunks from Gemini with automatic key rotation on 429 errors."""
        attempts = len(self.api_keys)

        for attempt in range(attempts):
            client = self._get_next_client()
            try:
                # Async streaming via client.aio
                response = await client.aio.models.generate_content_stream(
                    model="gemini-2.0-flash",
                    contents=prompt,
                )

                async for chunk in response:
                    if chunk.text:
                        yield chunk.text
                return  # Stream finished successfully

            except errors.APIError as e:
                if e.code == 429 or "RESOURCE_EXHAUSTED" in str(e):
                    print(
                        f"[Gemini Key Failover] 429 Exceeded Quota (Attempt {attempt+1}/{attempts}). Switching key..."
                    )
                    continue
                raise e
            except Exception as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    print("[Gemini Key Failover] 429 encountered. Rotating key...")
                    continue
                raise e

        raise Exception("All Gemini API keys hit quota limits. Please wait 60 seconds.")


gemini_service = GeminiClientPool()