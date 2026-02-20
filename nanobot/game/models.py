from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class DigimonState(Base):
    __tablename__ = "digimon_roster"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    species = Column(String)
    stage = Column(String)
    attribute = Column(String)
    element = Column(String)
    
    level = Column(Integer, default=1)
    exp = Column(Integer, default=0)
    
    max_hp = Column(Integer, default=100)
    current_hp = Column(Integer, default=100)
    
    hunger = Column(Integer, default=100)
    energy = Column(Integer, default=100)
    bond = Column(Integer, default=0)
    care_mistakes = Column(Integer, default=0)
    
    status_effects = Column(JSON, default=list) # e.g. ["Encouraged", "Sick"]
    equipped_items = Column(JSON, default=list)
    
    is_active = Column(Boolean, default=False)
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    last_updated = Column(String, default=lambda: datetime.utcnow().isoformat())
    hatch_time = Column(String, nullable=True)

class Inventory(Base):
    __tablename__ = "inventory"
    
    id = Column(Integer, primary_key=True, index=True)
    bits = Column(Integer, default=0)
    items = Column(JSON, default=dict) # {"Meat": 5, "Bandage": 2}
    crests = Column(JSON, default=list) # ["Courage"]
    digimentals = Column(JSON, default=list)

class TaskSyncState(Base):
    __tablename__ = "task_sync_state"
    
    id = Column(String, primary_key=True, index=True) # External task ID
    source = Column(String) # "google_tasks" or "notion"
    title = Column(String)
    due_date = Column(String, nullable=True)
    status = Column(String) # "pending", "completed", "overdue"
    attribute = Column(String) # "Vaccine", "Virus", "Data" based on tags
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    updated_at = Column(String, default=lambda: datetime.utcnow().isoformat())

class GuardrailState(Base):
    __tablename__ = "guardrails"
    
    date_str = Column(String, primary_key=True) # e.g., "2026-02-20"
    daily_input_tokens = Column(Integer, default=0)
    daily_output_tokens = Column(Integer, default=0)
    cost_estimate = Column(Float, default=0.0)

# Second Brain RA-H OS schema
class SecondBrainNode(Base):
    __tablename__ = "nodes"
    
    id = Column(String, primary_key=True)
    type = Column(String, nullable=False)
    name = Column(String, nullable=False)
    properties = Column(JSON, default=dict)
    
class SecondBrainEdge(Base):
    __tablename__ = "edges"
    
    id = Column(String, primary_key=True)
    source_id = Column(String, ForeignKey("nodes.id"))
    target_id = Column(String, ForeignKey("nodes.id"))
    relation = Column(String, nullable=False)
    properties = Column(JSON, default=dict)
    
class SecondBrainDimension(Base):
    __tablename__ = "dimensions"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
