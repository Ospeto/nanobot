from sqlalchemy.orm import Session
from datetime import datetime
from . import models, schemas

def get_or_create_inventory(db: Session) -> models.Inventory:
    inv = db.query(models.Inventory).first()
    if not inv:
        inv = models.Inventory(bits=0, items={}, crests=[], digimentals=[])
        db.add(inv)
        db.commit()
        db.refresh(inv)
    return inv

def get_active_digimon(db: Session) -> models.DigimonState:
    digi = db.query(models.DigimonState).filter(models.DigimonState.is_active == True).first()
    return digi

def set_active_digimon(db: Session, digimon_id: int):
    # de-activate all
    db.query(models.DigimonState).update({"is_active": False})
    # activate target
    target = db.query(models.DigimonState).filter(models.DigimonState.id == digimon_id).first()
    if target:
        target.is_active = True
        db.commit()
        db.refresh(target)
    return target

def add_digimon(db: Session, digimon: schemas.DigimonCreate) -> models.DigimonState:
    db_digimon = models.DigimonState(**digimon.model_dump())
    db.add(db_digimon)
    db.commit()
    db.refresh(db_digimon)
    
    # If it's the first one, make it active
    if db.query(models.DigimonState).count() == 1:
        db_digimon.is_active = True
        db.commit()
        
    return db_digimon

def update_guardrails(db: Session, input_tokens: int, output_tokens: int, cost: float):
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    rail = db.query(models.GuardrailState).filter(models.GuardrailState.date_str == date_str).first()
    if not rail:
        rail = models.GuardrailState(date_str=date_str)
        db.add(rail)
        
    rail.daily_input_tokens += input_tokens
    rail.daily_output_tokens += output_tokens
    rail.cost_estimate += cost
    db.commit()

def check_guardrails(db: Session, max_cost: float = 0.5) -> bool:
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    rail = db.query(models.GuardrailState).filter(models.GuardrailState.date_str == date_str).first()
    if not rail:
        return True # Safe
    if rail.cost_estimate >= max_cost:
        return False
    return True
