from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime

class DigimonBase(BaseModel):
    name: str
    species: str
    stage: str
    attribute: str
    element: str
    
class DigimonCreate(DigimonBase):
    pass

class DigimonResponse(DigimonBase):
    id: int
    level: int
    exp: int
    max_hp: int
    current_hp: int
    hunger: int
    energy: int
    bond: int
    care_mistakes: int
    status_effects: List[str]
    equipped_items: List[dict]
    is_active: bool
    created_at: str
    last_updated: str
    
    class Config:
        from_attributes = True

class InventoryResponse(BaseModel):
    id: int
    bits: int
    items: Dict[str, int]
    crests: List[str]
    digimentals: List[str]
    
    class Config:
        from_attributes = True

class GuardrailResponse(BaseModel):
    date_str: str
    daily_input_tokens: int
    daily_output_tokens: int
    cost_estimate: float
    
    class Config:
        from_attributes = True

class TaskSyncStateBase(BaseModel):
    id: str
    source: str
    title: str
    due_date: Optional[str] = None
    status: str
    attribute: str
    
class TaskSyncStateResponse(TaskSyncStateBase):
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True

class SecondBrainNodeBase(BaseModel):
    id: str
    type: str
    name: str
    properties: dict = {}

class SecondBrainEdgeBase(BaseModel):
    id: str
    source_id: str
    target_id: str
    relation: str
    properties: dict = {}
