import os
import itertools
import asyncio
from typing import AsyncGenerator, List
from google import genai
from google.genai import errors
from app.core.config import settings

# Primary and Fallback Models
PRIMARY_MODEL = "gemini-2.0-flash"  # Ensure this matches valid current model names
FALLBACK_MODEL = "gemini-1.5-flash"

class GeminiClientPool:
    def __init__(self):
        raw_keys = getattr(settings, "GEMINI_API_KEYS", "") or os.getenv("GEMINI_API_KEYS", "")
        if not raw_keys and hasattr(settings, "GEMINI_API_KEY"):
            raw_keys = settings.GEMINI_API_KEY

        self.api_keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
        if not self.api_keys:
            raise ValueError("No Gemini API keys configured in environment.")

        self._key_cycle = itertools.cycle(self.api_keys)

    def _get_next_client(self) -> genai.Client:
        key = next(self._key_cycle)
        return genai.Client(api_key=key)

    async def get_embedding(self, text: str) -> List[float]:
        """Generates text embeddings for Redis Semantic Caching."""
        attempts = len(self.api_keys)
        for _ in range(attempts):
            client = self._get_next_client()
            try:
                response = await client.aio.models.embed_content(
                    model="text-embedding-004",
                    contents=text,
                )
                return response.embedding.values
            except Exception as e:
                print(f"[Embedding Error] Rotating key... Details: {e}")
                await asyncio.sleep(0.2)
        raise Exception("All API keys failed for embedding generation.")

    async def stream_response(self, prompt: str) -> AsyncGenerator[str, None]:
        attempts = len(self.api_keys) * 2  # Try each key with primary, then fallback model

        for attempt in range(attempts):
            client = self._get_next_client()
            model_to_use = PRIMARY_MODEL if attempt < len(self.api_keys) else FALLBACK_MODEL

            try:
                response = await client.aio.models.generate_content_stream(
                    model=model_to_use,
                    contents=prompt,
                )

                async for chunk in response:
                    if chunk.text:
                        yield chunk.text
                return

            except errors.APIError as e:
                print(f"[Gemini Error] Code {e.code} using {model_to_use}. Rotating key...")
                await asyncio.sleep(0.5)  # Backoff to avoid instantly burning TPM/RPM
                continue
            except Exception as e:
                print(f"[Gemini Exception] {e}. Rotating key...")
                await asyncio.sleep(0.5)
                continue

        raise Exception("All API keys hit quota limits or models were unresponsive. Please retry in 60 seconds.")

gemini_service = GeminiClientPool()