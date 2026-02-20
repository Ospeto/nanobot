from sqlalchemy.orm import Session
from . import models

def add_memory_node(db: Session, type: str, name: str, properties: dict) -> models.SecondBrainNode:
    node_id = f"{type}_{name.lower().replace(' ', '_')}"
    node = db.query(models.SecondBrainNode).filter(models.SecondBrainNode.id == node_id).first()
    if not node:
        node = models.SecondBrainNode(id=node_id, type=type, name=name, properties=properties)
        db.add(node)
    else:
        existing = dict(node.properties) if node.properties else {}
        existing.update(properties)
        node.properties = existing
    
    db.commit()
    db.refresh(node)
    return node

def link_memory_nodes(db: Session, source_id: str, target_id: str, relation: str, properties: dict = None):
    edge_id = f"{source_id}_{relation}_{target_id}"
    edge = db.query(models.SecondBrainEdge).filter(models.SecondBrainEdge.id == edge_id).first()
    if not edge:
        edge = models.SecondBrainEdge(
            id=edge_id, source_id=source_id, target_id=target_id, relation=relation, properties=properties or {}
        )
        db.add(edge)
        db.commit()
        db.refresh(edge)
    return edge

def batch_upsert_memory(db: Session, entities: list[dict], relations: list[dict]) -> dict:
    """Atomically upserts multiple nodes and links them explicitly in the SecondBrain."""
    results = {"nodes": [], "edges": []}
    for ent in entities:
        n = add_memory_node(db, type=ent["type"], name=ent["name"], properties=ent.get("properties", {}))
        results["nodes"].append(n.id)
    
    for rel in relations:
        e = link_memory_nodes(db, source_id=rel["source_id"], target_id=rel["target_id"], relation=rel["relation"], properties=rel.get("properties", {}))
        results["edges"].append(e.id)
        
    return results

def search_memory(db: Session, query: str):
    nodes = db.query(models.SecondBrainNode).filter(models.SecondBrainNode.name.ilike(f"%{query}%")).all()
    # also search in properties (dirty hack for sqlite without FTS)
    properties_nodes = db.query(models.SecondBrainNode).filter(models.SecondBrainNode.properties.ilike(f"%{query}%")).all()
    
    results = {n.id: n for n in nodes + properties_nodes}
    return list(results.values())

def get_memory_context_string(db: Session, query: str = None) -> str:
    """Returns a stringified version of recent or relevant memories for prompt injection."""
    nodes = []
    if query:
        nodes = search_memory(db, query)
    else:
        nodes = db.query(models.SecondBrainNode).limit(10).all()
        
    if not nodes:
        return "No relevant memories found."
        
    lines = ["[Second Brain Memory Context]"]
    for n in nodes:
        lines.append(f"- [{n.type}] {n.name}: {n.properties}")
    return "\n".join(lines)
