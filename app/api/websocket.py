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
            raw_data = await websocket.receive_text()
            
            # Safe JSON decoding for string or structured payload
            try:
                payload = json.loads(raw_data)
            except Exception:
                payload = {"prompt": raw_data}

            prompt = payload.get("prompt", "").strip()
            doc_context = payload.get("document_context")
            doc_name = payload.get("document_name")

            if not prompt:
                await websocket.send_json({"type": "error", "message": "Empty prompt"})
                continue

            # 1. Compute embedding ONLY on the user query for accurate Cache Matching
            query_embedding = await gemini_service.get_embedding(prompt)

            # 2. Check Redis Semantic Cache when no active document context is forced
            if not doc_context:
                cached_response, similarity = await semantic_cache.search(query_embedding, threshold=0.92)
                if cached_response:
                    await websocket.send_json({
                        "type": "start",
                        "engine": f"Redis Semantic Cache (Similarity: {similarity:.2%})"
                    })
                    await websocket.send_json({"type": "chunk", "content": cached_response})
                    await websocket.send_json({"type": "end"})
                    continue

            # 3. Build LLM System Prompt + User Query + Document Context
            if doc_context:
                full_prompt = f"""You are Nexus Copilot, an AI assistant. Analyze the provided document context and directly answer the user's question.

### DOCUMENT CONTEXT ({doc_name or 'Attached File'}):
{doc_context}

### USER QUESTION:
{prompt}

### INSTRUCTIONS:
1. Do NOT dump or repeat the raw document.
2. Answer the user question directly using facts from the document context.
3. If the context does not contain the answer, explicitly state that."""
            else:
                full_prompt = prompt

            # 4. Stream response via Gemini API
            await websocket.send_json({"type": "start", "engine": "Cloud Gemini Gateway"})
            full_response = ""

            async for chunk in gemini_service.stream_response(full_prompt):
                full_response += chunk
                await websocket.send_json({"type": "chunk", "content": chunk})

            # 5. Store Cache Entry (only for non-document context standard queries)
            if not doc_context:
                cache_id = str(uuid.uuid4())
                await semantic_cache.store(cache_id, prompt, full_response, query_embedding)

            await websocket.send_json({"type": "end"})

    except WebSocketDisconnect:
        print("Client disconnected from WebSocket connection")
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})
        await websocket.close()