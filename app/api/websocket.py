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
            
            # Safe JSON parsing
            try:
                payload = json.loads(raw_data)
            except Exception:
                payload = {"prompt": raw_data}

            # 1. HANDLE PING / CONTROL FRAMES
            msg_type = payload.get("type")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            prompt = payload.get("prompt", "").strip()
            doc_context = payload.get("document_context")
            doc_name = payload.get("document_name")

            if not prompt:
                await websocket.send_json({"type": "error", "message": "Empty prompt"})
                continue

            # 2. EMBEDDING & CACHE MATCHING
            # Only hit cache if NO active document context is forced
            if not doc_context:
                try:
                    query_embedding = await gemini_service.get_embedding(prompt)
                    cached_response, similarity = await semantic_cache.search(query_embedding, threshold=0.92)
                    if cached_response:
                        await websocket.send_json({
                            "type": "start",
                            "engine": f"Redis Semantic Cache (Similarity: {similarity:.2%})"
                        })
                        await websocket.send_json({"type": "chunk", "content": cached_response})
                        await websocket.send_json({"type": "end"})
                        continue
                except Exception as cache_err:
                    print(f"Cache/Embedding error: {cache_err}")
                    query_embedding = None
            else:
                query_embedding = None

            # 3. PROMPT CONSTRUCTION
            if doc_context:
                full_prompt = f"""You are Nexus Copilot, an AI assistant. Analyze the provided document context and answer the user's question.

DOCUMENT NAME: {doc_name or 'Attached File'}

DOCUMENT CONTEXT:
{doc_context}

USER QUESTION:
{prompt}

INSTRUCTIONS:
- Directly answer the question using the facts provided in the DOCUMENT CONTEXT above.
- Do NOT repeat or dump the full document.
- Provide clear, synthesis-driven answers.
- If the context does not contain the information required to answer, clearly state that."""
            else:
                full_prompt = prompt

            # 4. STREAM GEMINI RESPONSE
            await websocket.send_json({"type": "start", "engine": "Cloud Gemini Gateway"})
            full_response = ""

            try:
                async for chunk in gemini_service.stream_response(full_prompt):
                    full_response += chunk
                    await websocket.send_json({"type": "chunk", "content": chunk})

                # 5. STORE CACHE
                if not doc_context and query_embedding:
                    cache_id = str(uuid.uuid4())
                    await semantic_cache.store(cache_id, prompt, full_response, query_embedding)

            except Exception as stream_err:
                await websocket.send_json({"type": "error", "message": f"Gemini Stream Error: {str(stream_err)}"})

            await websocket.send_json({"type": "end"})

    except WebSocketDisconnect:
        print("Client disconnected from WebSocket connection")
    except Exception as e:
        print(f"Unhandled WebSocket Exception: {e}")