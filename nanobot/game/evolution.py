from sqlalchemy.orm import Session
from . import state
from .encyclopedia import Digipedia
from nanobot.game.models import EvolutionRule
from nanobot.game.database import SessionLocal
from nanobot.config.loader import load_config
from nanobot.cli.commands import _make_provider

async def generate_evolution_conditions(base_name: str, target_name: str) -> None:
    db = SessionLocal()
    try:
        # Prevent race condition duplicates
        rule = db.query(EvolutionRule).filter_by(base_digimon=base_name, target_digimon=target_name).first()
        if rule:
            return
            
        config = load_config()
        provider = _make_provider(config)
        prompt = f"""You are a specialized game designer for a Digimon Virtual Pet simulation.
Your task is to generate exactly 1 concise evolution requirement for evolving '{base_name}' into '{target_name}'.
You must choose from one or a combination of the following virtual pet game mechanics:
- Care Mistakes (e.g., "0-2 Care Mistakes")
- Bond/Affection (e.g., "High Bond 50+")
- Battles Won (e.g., "5+ Battles Won")
- Weight (e.g., "Weight > 20g")

Do not write any introductory or wrap-up text. Return ONLY the condition string itself. Limit to 30 characters maximum!
Example: "High Bond & 0 Care Mistakes"
"""
        response = await provider.chat([{"role": "user", "content": prompt}], max_tokens=50)
        
        condition_string = response.content.strip().strip('"\'')
        if response.finish_reason == "error" or condition_string.startswith("Error calling LLM:"):
            raise ValueError(f"LLM returned error: {condition_string}")

        if len(condition_string) > 40:
            condition_string = condition_string[:37] + "..."
            
        new_rule = EvolutionRule(
            base_digimon=base_name,
            target_digimon=target_name,
            condition_string=condition_string
        )
        db.add(new_rule)
        db.commit()
    except Exception as e:
        import traceback
        print(f"LLM Generation failed for {target_name}, using fallback heuristics. ({e})")
        
        target_hash = sum(ord(c) for c in target_name)
        if target_hash % 3 == 0:
            condition_string = "High Bond (50+)"
        elif target_hash % 3 == 1:
            condition_string = "Low Care Mistakes"
        else:
            condition_string = "Battle Rank C+"
            
        new_rule = EvolutionRule(
            base_digimon=base_name,
            target_digimon=target_name,
            condition_string=condition_string
        )
        db.add(new_rule)
        db.commit()
    finally:
        db.close()

async def verify_evolution_requirements(db: Session, active, target_name: str, target_stage: str) -> dict:
    """
    Returns {"can_evolve": bool, "reason": str} defining if the given active Digimon can evolve into target.
    """
    inv = state.get_or_create_inventory(db)
    target_stage_clean = str(target_stage or "").lower()
    
    api_to_internal = {
        "child": "rookie",
        "adult": "champion",
        "perfect": "ultimate",
        "ultimate": "mega"
    }
    target_stage_clean = api_to_internal.get(target_stage_clean, target_stage_clean)

    # Hidden / Special Evolution Check (X-Antibody)
    if target_name.endswith(" X") or "X-Antibody" in target_name:
        if "X-Antibody" in inv.items and inv.items["X-Antibody"] > 0:
            return {"can_evolve": True, "reason": "X-Antibody Resonance Detected"}
        else:
            return {"can_evolve": False, "reason": "Requires X-Antibody Item"}
            
    # Crest Logic for specific branches (e.g., Flamedramon requires Digimental of Courage)
    # We will expand this as needed, but for now allow specific text targets:
    if "Crest" in target_name or "Magnamon" in target_name or "Flamedramon" in target_name:
        if any("Courage" in c for c in inv.digimentals + inv.crests):
            return {"can_evolve": True, "reason": "Crest/Digimental Resonance Detected"}
        else:
            return {"can_evolve": False, "reason": "Requires Special Item"}

    # Standard Math Firewall Checks
    if target_stage_clean == "baby ii":
        if active.level >= 3:
            return {"can_evolve": True, "reason": "Level Requirement Met"}
        return {"can_evolve": False, "reason": "Requires Level 3+"}
        
    elif target_stage_clean == "rookie":
        if active.level >= 10 and active.bond >= 20:
            return {"can_evolve": True, "reason": "Level & Bond Met"}
        return {"can_evolve": False, "reason": "Req Level 10+, Bond 20+"}
        
    elif target_stage_clean == "champion":
        if active.level >= 20 and active.bond >= 50:
            return {"can_evolve": True, "reason": "Level & Bond Met"}
        return {"can_evolve": False, "reason": "Req Level 20+, Bond 50+"}
        
    elif target_stage_clean == "ultimate":
        if active.level >= 40 and active.bond >= 80:
            return {"can_evolve": True, "reason": "Level & Bond Met"}
        return {"can_evolve": False, "reason": "Req Level 40+, Bond 80+"}
        
    elif target_stage_clean == "mega" or target_stage_clean == "ultra":
        if active.level >= 60 and active.bond >= 100:
            return {"can_evolve": True, "reason": "Max Bond Reached"}
        return {"can_evolve": False, "reason": "Req Level 60+, Bond 100"}

    # Fallback to true for unknown targets that slip through purely based on high levels
    if active.level > 25:
        return {"can_evolve": True, "reason": "High Level Override"}
        
    return {"can_evolve": False, "reason": "Requirements Not Met"}


async def execute_evolution(db: Session, active, target_name: str) -> dict:
    """
    Executes the deterministic state mutation, evolving the active digimon.
    """
    target_info = await Digipedia.get_digimon_info(target_name)
    if not target_info:
        return {"success": False, "error": "Target Digimon data missing from compendium."}

    target_level_list = target_info.get("levels", [])
    target_stage = target_level_list[0] if target_level_list else target_info.get("level", "")
    
    validation = await verify_evolution_requirements(db, active, target_name, target_stage)
    if not validation["can_evolve"]:
        return {"success": False, "error": validation["reason"]}
        
    inv = state.get_or_create_inventory(db)
    
    # Consume Special Items if it was an item evolution
    if target_name.endswith(" X") or "X-Antibody" in target_name:
        if "X-Antibody" in inv.items and inv.items["X-Antibody"] > 0:
            inv.items["X-Antibody"] -= 1

    # Mutate State
    active.species = target_name
    active.name = target_name
    active.stage = target_stage
    
    # Reset level mechanically but bump max bounds
    active.level = 1
    active.bond = int(active.bond / 2) # Halve bond to simulate evolving shock
    active.exp = 0
    active.max_hp = active.max_hp + 100
    active.current_hp = active.max_hp
    active.energy = 100
    active.hunger = 100
    
    # Set element logic safely
    elements = target_info.get("skills", [])
    if elements:
        active.element = elements[0].get("attribute", active.element)
        
    attributes = target_info.get("attributes", [])
    if attributes:
        active.attribute = attributes[0].get("attribute", active.attribute)
        
    db.commit()
    db.refresh(active)
    
    return {"success": True, "message": f"Evolved into {target_name}!", "new_stage": target_stage}

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

