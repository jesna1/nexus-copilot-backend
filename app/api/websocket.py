from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.gemini_client import gemini_service
from app.services.semantic_cache import semantic_cache
import json
import uuid

router = APIRouter()

@router.websocket("/ws/chat")
async def websocket_chat_endpoint(websocket: WebSocket):
    await websocket.accept()
    await semantic_cache.init_index()

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            prompt = payload.get("prompt", "")

            if not prompt:
                await websocket.send_json({"type": "error", "message": "Empty prompt"})
                continue

            # 1. Generate query embedding
            query_embedding = await gemini_service.get_embedding(prompt)

            # 2. Check Redis Semantic Cache
            cached_response, similarity = await semantic_cache.search(query_embedding, threshold=0.92)

            if cached_response:
                # CACHE HIT (<50ms response)
                await websocket.send_json({
                    "type": "start",
                    "engine": f"Redis Semantic Cache (Similarity: {similarity:.2%})"
                })
                await websocket.send_json({"type": "chunk", "content": cached_response})
                await websocket.send_json({"type": "end"})
                continue

            # 3. CACHE MISS -> Call Gemini LLM & Stream Response
            await websocket.send_json({"type": "start", "engine": "Cloud Gemini Gateway"})
            full_response = ""

            async for chunk in gemini_service.stream_response(prompt):
                full_response += chunk
                await websocket.send_json({"type": "chunk", "content": chunk})

            # 4. Write back to Redis Cache for future requests
            cache_id = str(uuid.uuid4())
            await semantic_cache.store(cache_id, prompt, full_response, query_embedding)

            await websocket.send_json({"type": "end"})

    except WebSocketDisconnect:
        print("Client disconnected from WebSocket connection")
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})
        await websocket.close()