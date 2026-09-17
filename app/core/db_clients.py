from neo4j import AsyncGraphDatabase
import asyncpg
from app.core.config import settings

class DatabaseClients:
    def __init__(self):
        self.neo4j_driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
        self.pg_pool = None

    async def init_pgvector(self):
        """Initialize PostgreSQL pool and vector extension."""
        self.pg_pool = await asyncpg.create_pool(
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            database=settings.POSTGRES_DB,
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT
        )
        async with self.pg_pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    doc_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    embedding vector(3072)
                );
            """)

    async def close(self):
        await self.neo4j_driver.close()
        if self.pg_pool:
            await self.pg_pool.close()

db_clients = DatabaseClients()