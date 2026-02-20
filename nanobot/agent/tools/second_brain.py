from typing import Any
import json
from pydantic import Field
from sqlalchemy.orm import Session

from nanobot.agent.tools.base import Tool
from nanobot.game.database import SessionLocal
from nanobot.game import memory


class ManageMemoryGraphTool(Tool):
    """Tool to batch upsert entities and their relationships to the Digimon Second Brain."""
    
    name: str = "manage_memory_graph"
    description: str = "Adds or updates entities and relationships in the Digimon Second Brain graph. Use this to remember concepts, enemies, tasks explicitly. You can add multiple nodes and link them all at once (batch transaction)."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "entities": {
                "type": "array",
                "description": "List of entities to upsert.",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "description": "Type of the node (e.g., 'concept', 'enemy', 'person')"},
                        "name": {"type": "string", "description": "Name of the entity"},
                        "properties": {"type": "object", "description": "JSON object with details", "additionalProperties": True}
                    },
                    "required": ["type", "name"]
                }
            },
            "relations": {
                "type": "array",
                "description": "List of links/edges between entities. The exact ID is usually 'type_name' generated from the types and names.",
                "items": {
                    "type": "object",
                    "properties": {
                        "source_id": {"type": "string", "description": "Exact ID of source node"},
                        "target_id": {"type": "string", "description": "Exact ID of target node"},
                        "relation": {"type": "string", "description": "The relationship (e.g., 'weak_to', 'knows')"}
                    },
                    "required": ["source_id", "target_id", "relation"]
                }
            }
        },
        "required": ["entities", "relations"]
    }

    async def execute(self, arguments: dict[str, Any]) -> str:
        db = SessionLocal()
        try:
            res = memory.batch_upsert_memory(
                db=db,
                entities=arguments.get("entities", []),
                relations=arguments.get("relations", [])
            )
            return f"Successfully saved to memory: {len(res['nodes'])} nodes and {len(res['edges'])} edges."
        except Exception as e:
            import logging
            logging.error(f"Error managing memory graph: {e}")
            return f"Error adding memory: {str(e)}"
        finally:
            db.close()


class SearchMemoryGraphTool(Tool):
    """Tool to search the Digimon Second Brain graph for information."""
    
    name: str = "search_memory_graph"
    description: str = "Searches the Second Brain SQL Graph explicitly for a query to remember lore, enemies, etc."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The focus keyword to search for."
            }
        },
        "required": ["query"]
    }

    async def execute(self, arguments: dict[str, Any]) -> str:
        db = SessionLocal()
        try:
            nodes = memory.search_memory(db, query=arguments["query"])
            if not nodes:
                return f"No memories found for '{arguments['query']}'."
                
            out = []
            for n in nodes:
                out.append(f"Node [ID: {n.id}, Type: {n.type}, Name: {n.name}] -> {json.dumps(n.properties)}")
                
            return "\n".join(out)
        except Exception as e:
            return f"Error searching memory: {str(e)}"
        finally:
            db.close()
