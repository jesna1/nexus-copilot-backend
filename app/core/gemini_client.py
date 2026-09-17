from google import genai
from app.core.config import settings

class GeminiClient:
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    async def stream_response(self, prompt: str):
        response = await self.client.aio.models.generate_content_stream(
            model="gemini-3.6-flash",
            contents=prompt,
        )
        async for chunk in response:
            if chunk.text:
                yield chunk.text

    async def get_embedding(self, text: str) -> list[float]:
        response = await self.client.aio.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
        )
        return response.embeddings[0].values

gemini_service = GeminiClient()