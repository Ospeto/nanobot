from sqlalchemy.orm import Session
from . import state
from .encyclopedia import Digipedia

async def check_evolution_ready(db: Session) -> dict:
    digi = state.get_active_digimon(db)
    if not digi:
        return {"error": "No active digimon"}
        
    info = await Digipedia.get_digimon_info(digi.name)
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

def hatch_digitama(weather: str, hour: int) -> dict:
    """
    Determines the Base Baby I Digimon returned from a Digitama (Egg)
    based on local time and current weather conditions.
    """
    # Time classifications
    is_dawn = 6 <= hour < 12
    is_day = 12 <= hour < 18
    is_dusk = 18 <= hour < 21
    is_night = hour >= 21 or hour < 6

    # Start with base scores for the Baby I roster
    scores = {
        "Botamon": 0,       # Reptile / Classic
        "Poyomon": 0,       # Holy / Angelic
        "Punimon": 0,       # Beast / Data
        "Pichimon": 0,      # Aquatic
        "YukimiBotamon": 0, # Ice
        "Zurumon": 0,       # Dark / Virus
        "Kuramon": 0        # Dark / Cyber
    }

    # Apply Time Modifiers
    if is_dawn:
        scores["Poyomon"] += 3
        scores["Botamon"] += 1
    elif is_day:
        scores["Botamon"] += 3
        scores["Punimon"] += 3
    elif is_dusk:
        scores["Zurumon"] += 2
        scores["Kuramon"] += 2
    elif is_night:
        scores["Zurumon"] += 4
        scores["Kuramon"] += 4

    # Apply Weather Modifiers
    if weather == "Clear":
        scores["Botamon"] += 3
        scores["Poyomon"] += 2
    elif weather == "Rain":
        scores["Pichimon"] += 6 # High bias for rain
        scores["Zurumon"] += 1
    elif weather == "Cloudy":
        scores["Punimon"] += 3
        scores["Kuramon"] += 1
    elif weather == "Snow":
        scores["YukimiBotamon"] += 8 # Huge bias for snow

    # Find the Digimon with the highest score
    # If tie, alphabetically sorting dict keys acts as deterministic tiebreaker,
    # or we can just max() using a standard key
    winner = max(scores.items(), key=lambda x: x[1])[0]
    
    # Map winner to Base Attributes for initialization
    baseline_stats = {
        "Botamon": {"attribute": "Data", "element": "Fire"},
        "Poyomon": {"attribute": "Data", "element": "Light"},
        "Punimon": {"attribute": "Data", "element": "Earth"},
        "Pichimon": {"attribute": "Data", "element": "Water"},
        "YukimiBotamon": {"attribute": "Data", "element": "Ice"},
        "Zurumon": {"attribute": "Virus", "element": "Dark"},
        "Kuramon": {"attribute": "Unknown", "element": "Dark"}
    }
    
    return {
        "species": winner,
        "name": winner,
        "stage": "Baby I",
        "level": 1,
        "attribute": baseline_stats[winner]["attribute"],
        "element": baseline_stats[winner]["element"]
    }

