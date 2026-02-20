import random
from typing import Dict, Any
from sqlalchemy.orm import Session
from . import state

class Enemy:
    def __init__(self, task_source: str, task_id: str, title: str, status: str, difficulty: int = 1):
        self.task_source = task_source
        self.task_id = task_id
        self.title = title
        self.status = status
        self.difficulty = difficulty
        
        self.attribute = random.choice(["Vaccine", "Data", "Virus"])

def resolve_combat(db: Session, enemy: Enemy) -> dict:
    """
    Called when a task is completed. Grants rewards to the active Digimon.
    """
    digi = state.get_active_digimon(db)
    if not digi:
        return {"error": "No active partner"}
        
    exp_gain = 10 * enemy.difficulty
    bits_gain = 50 * enemy.difficulty
    bond_gain = 2
    
    advantage = False
    disadvantage = False
    
    if digi.attribute == "Vaccine" and enemy.attribute == "Virus": advantage = True
    elif digi.attribute == "Virus" and enemy.attribute == "Data": advantage = True
    elif digi.attribute == "Data" and enemy.attribute == "Vaccine": advantage = True
    elif digi.attribute == "Virus" and enemy.attribute == "Vaccine": disadvantage = True
    elif digi.attribute == "Data" and enemy.attribute == "Virus": disadvantage = True
    elif digi.attribute == "Vaccine" and enemy.attribute == "Data": disadvantage = True
    
    if advantage:
        exp_gain = int(exp_gain * 1.5)
        bits_gain = int(bits_gain * 1.5)
    elif disadvantage:
        exp_gain = int(exp_gain * 0.8)
        bits_gain = int(bits_gain * 0.8)
        
    digi.exp += exp_gain
    digi.bond += bond_gain
    
    level_up = False
    while digi.exp >= digi.level * 100:
        digi.exp -= digi.level * 100
        digi.level += 1
        digi.max_hp += 10
        digi.current_hp = digi.max_hp
        level_up = True
        
    inv = state.get_or_create_inventory(db)
    inv.bits += bits_gain
    
    db.commit()
    
    return {
        "exp": exp_gain,
        "bits": bits_gain,
        "bond": bond_gain,
        "advantage": advantage,
        "level_up": level_up,
        "new_level": digi.level
    }

def apply_overdue_penalty(db: Session, enemy: Enemy):
    """
    Called when a task is heavily overdue.
    Applies Dark Data corruption.
    """
    digi = state.get_active_digimon(db)
    if not digi:
        return
        
    digi.current_hp = max(0, digi.current_hp - 10)
    digi.care_mistakes += 1
    
    status = []
    if digi.status_effects:
        status = list(digi.status_effects)
        
    if "Sick" not in status:
        status.append("Sick")
        digi.status_effects = status
        
    db.commit()
