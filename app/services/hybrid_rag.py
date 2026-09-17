from app.core.db_clients import db_clients
from app.core.gemini_client import gemini_service

class HybridRAGEngine:
    async def search(self, query: str, top_k: int = 3) -> str:
        # 1. Dense Vector Search in pgvector
        query_embedding = await gemini_service.get_embedding(query)
        
        vector_results = []
        if db_clients.pg_pool:
            async with db_clients.pg_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT content FROM document_chunks
                    ORDER BY embedding <=> $1 LIMIT $2;
                """, str(query_embedding), top_k)
                vector_results = [r['content'] for r in rows]

        # 2. Graph Traversal in Neo4j
        graph_results = []
        async with db_clients.neo4j_driver.session() as session:
            # Extract key term from query for node matching
            terms = [w.lower() for w in query.split() if len(w) > 3]
            for term in terms:
                cypher = """
                MATCH (e:Entity {name: $term})-[r]->(target:Entity)
                RETURN e.name + ' ' + type(r) + ' ' + target.name AS fact LIMIT 5
                """
                result = await session.run(cypher, term=term)
                records = await result.data()
                graph_results.extend([rec['fact'] for rec in records])

        # 3. Hybrid Context Fusion
        fused_context = "--- GRAPH KNOWLEDGE FACTS ---\n"
        fused_context += "\n".join(set(graph_results)) if graph_results else "No explicit graph relationships found."
        fused_context += "\n\n--- VECTOR DOCUMENT CHUNKS ---\n"
        fused_context += "\n\n".join(vector_results) if vector_results else "No vector chunks found."

        return fused_context

hybrid_rag = HybridRAGEngine()