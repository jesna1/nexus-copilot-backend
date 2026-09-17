import json
from pydantic import BaseModel
from app.core.gemini_client import gemini_service
from app.core.db_clients import db_clients

class Entity(BaseModel):
    name: str
    type: str

class Relationship(BaseModel):
    source: str
    target: str
    relation: str

class GraphKnowledge(BaseModel):
    entities: list[Entity]
    relationships: list[Relationship]

class GraphExtractor:
    async def extract_and_store(self, doc_id: str, text_chunk: str):
        prompt = (
            "Extract core entities and relationships from this document text.\n"
            "Return JSON with schema:\n"
            "{\n"
            '  "entities": [{"name": "...", "type": "..."}],\n'
            '  "relationships": [{"source": "...", "target": "...", "relation": "..."}]\n'
            "}\n"
            f"Text: {text_chunk}"
        )
        
        # Call Gemini model
        response_text = ""
        async for chunk in gemini_service.stream_response(prompt):
            response_text += chunk

        try:
            cleaned_json = response_text.replace("```json", "").replace("```", "").strip()
            data = json.loads(cleaned_json)
            knowledge = GraphKnowledge(**data)
        except Exception:
            return

        # Store in Neo4j
        async with db_clients.neo4j_driver.session() as session:
            for entity in knowledge.entities:
                await session.run(
                    "MERGE (e:Entity {name: $name}) ON CREATE SET e.type = $type, e.doc_id = $doc_id",
                    name=entity.name.lower(), type=entity.type, doc_id=doc_id
                )
            for rel in knowledge.relationships:
                cypher = (
                    "MATCH (a:Entity {name: $source}), (b:Entity {name: $target})\n"
                    "MERGE (a)-[r:RELATION {type: $relation, doc_id: $doc_id}]->(b)"
                )
                await session.run(
                    cypher,
                    source=rel.source.lower(),
                    target=rel.target.lower(),
                    relation=rel.relation.upper(),
                    doc_id=doc_id
                )

graph_extractor = GraphExtractor()