import asyncio
from app.core.db_clients import db_clients
from app.services.graph_extractor import graph_extractor
from app.services.hybrid_rag import hybrid_rag
from app.core.gemini_client import gemini_service

async def run_phase3_test():
    print("=== Step 1: Initializing PostgreSQL & Vector Extension ===")
    await db_clients.init_pgvector()

    doc_id = "doc_test_1"
    sample_text = (
        "High-voltage transformers require strict Lockout/Tagout (LOTO) procedures. "
        "The Buchholz relay operates as a gas-detection switch that prevents explosion. "
        "Dissolved Gas Analysis (DGA) monitors thermal insulation breakdown."
    )

    print("\n=== Step 2: Extracting Knowledge Graph into Neo4j ===")
    await graph_extractor.extract_and_store(doc_id, sample_text)
    print("Entity extraction and Cypher insertion complete.")

    print("\n=== Step 3: Storing Dense Embedding in pgvector ===")
    embedding = await gemini_service.get_embedding(sample_text)
    async with db_clients.pg_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO document_chunks (doc_id, content, embedding) VALUES ($1, $2, $3::vector)",
            doc_id, sample_text, str(embedding)
        )
    print("Vector stored successfully.")

    print("\n=== Step 4: Testing Hybrid RAG Context Fusion ===")
    query = "What safety switch detects gas in transformers?"
    fused_context = await hybrid_rag.search(query)

    print("\n---------------- FUSED RESULT ----------------")
    print(fused_context)
    print("----------------------------------------------")

    await db_clients.close()

if __name__ == "__main__":
    asyncio.run(run_phase3_test())