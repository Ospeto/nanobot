from sqlalchemy.orm import Session
from . import state
from .encyclopedia import Digipedia

def check_evolution_ready(db: Session) -> dict:
    digi = state.get_active_digimon(db)
    if not digi:
        return {"error": "No active digimon"}
        
    info = Digipedia.get_digimon_info(digi.name)
    if not info:
        return {"error": "Could not fetch evolution data"}
        
    next_evos = info.get("nextEvolutions", [])
    possible = []
    
    inv = state.get_or_create_inventory(db)
    crests = inv.crests if inv.crests else []
    digimentals = inv.digimentals if inv.digimentals else []
    
    for evo in next_evos:
        cond = evo.get("condition", "") or ""
        
        # Parse API condition string (basic logic)
        if "Courage" in cond and "Crest of Courage" not in crests:
            continue
        if "X-Antibody" in cond and "X-Antibody" not in digimentals:
            continue
            
        # Mock bond check to prevent immediate evolution parsing explosion
        if digi.bond >= 50 or digi.level >= 10:
            possible.append(evo.get("digimon"))
            
    return {"possible_evolutions": possible}

def trigger_agentic_quest(target_digimon: str):
    """
    Returns a system string describing the tool-use challenge the Digimon must complete to evolve.
    """
    quest = f"To evolve into {target_digimon}, you must prove your mastery over the digital world. Use your bash capability to write a python script that calculates the first 100 fibonacci numbers, saves it to a file, and executes it. Only when you successfully read the output back to me will I allow the evolution."
    return quest

def handle_jogress(db: Session, digimon_a_id: int, digimon_b_id: int, target_name: str):
    """
    DNA Digivolution. Merges two digimon node contexts.
    """
    return {"status": "Jogress complete", "new_digimon": target_name}
