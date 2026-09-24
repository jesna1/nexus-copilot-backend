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
            
            try:
                payload = json.loads(raw_data)
            except Exception:
                payload = {"prompt": raw_data}

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

            # Semantic Cache Check (skipped if document context is attached)
            query_embedding = None
            if not doc_context:
                try:
                    query_embedding = await gemini_service.get_embedding(prompt)
                    cached_response, similarity = await semantic_cache.search(query_embedding, threshold=0.92)
                    if cached_response:
                        await websocket.send_json({
                            "type": "start",
                            "engine": f"Redis Semantic Cache ({similarity:.1%})"
                        })
                        await websocket.send_json({"type": "chunk", "content": cached_response})
                        await websocket.send_json({"type": "end"})
                        continue
                except Exception as cache_err:
                    print(f"[Cache Error] {cache_err}")

            # Context Truncation to save TPM Quota
            if doc_context:
                max_chars = 15000
                truncated_doc = doc_context[:max_chars] if len(doc_context) > max_chars else doc_context
                full_prompt = f"""You are Nexus Copilot, an AI assistant. Analyze the document context below and answer the user's prompt.

DOCUMENT NAME: {doc_name or 'Attached File'}

DOCUMENT CONTEXT:
{truncated_doc}

USER QUESTION:
{prompt}

INSTRUCTIONS:
- Directly answer using facts from the document context.
- If the document does not contain the answer, explicitly state that."""
            else:
                full_prompt = prompt

            # Stream Gemini Generation
            await websocket.send_json({"type": "start", "engine": "Cloud Gemini Gateway"})
            full_response = ""

            try:
                async for chunk in gemini_service.stream_response(full_prompt):
                    full_response += chunk
                    await websocket.send_json({"type": "chunk", "content": chunk})

                if not doc_context and query_embedding:
                    cache_id = str(uuid.uuid4())
                    await semantic_cache.store(cache_id, prompt, full_response, query_embedding)

            except Exception as stream_err:
                await websocket.send_json({"type": "error", "message": f"Gemini Error: {str(stream_err)}"})

            await websocket.send_json({"type": "end"})

    except WebSocketDisconnect:
        print("Client disconnected from WebSocket.")
    except Exception as e:
        print(f"Unhandled WebSocket exception: {e}")