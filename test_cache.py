import asyncio
import json
import websockets

async def test_semantic_cache():
    uri = "ws://localhost:8000/ws/chat"
    
    async with websockets.connect(uri) as ws:
        # 1. First Execution: Expect CACHE MISS (Cloud Gemini Gateway)
        print("\n=== Test 1: First Execution (Cache Miss) ===")
        await ws.send(json.dumps({"prompt": "What is high-voltage transformer safety?"}))
        
        while True:
            try:
                msg = await ws.recv()
                response = json.loads(msg)
            except websockets.exceptions.ConnectionClosed:
                print("\n[Connection closed by server]")
                break

            if response.get("type") == "error":
                print(f"\n[Backend Error]: {response.get('message')}")
                return
            elif response.get("type") == "start":
                print(f"Engine: {response.get('engine')}")
            elif response.get("type") == "chunk":
                print(response.get("content", ""), end="", flush=True)
            elif response.get("type") == "end":
                print("\n[Stream Complete]")
                break

        # 2. Second Execution: Expect CACHE HIT (Redis Semantic Cache)
        print("\n=== Test 2: Similar Execution (Cache Hit) ===")
        await ws.send(json.dumps({"prompt": "Tell me the safety rules for high voltage transformers."}))
        
        while True:
            try:
                msg = await ws.recv()
                response = json.loads(msg)
            except websockets.exceptions.ConnectionClosed:
                print("\n[Connection closed by server]")
                break

            if response.get("type") == "error":
                print(f"\n[Backend Error]: {response.get('message')}")
                return
            elif response.get("type") == "start":
                print(f"Engine: {response.get('engine')}")
            elif response.get("type") == "chunk":
                print(f"Cached Result: {response.get('content')}")
            elif response.get("type") == "end":
                print("[Stream Complete]")
                break

if __name__ == "__main__":
    asyncio.run(test_semantic_cache())