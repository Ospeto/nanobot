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

    target_info = await Digipedia.get_digimon_info(target_name)
    if not target_info:
        return {"can_evolve": False, "reason": "Target Digimon data missing."}
        
    target_attribute = str(target_info.get("attributes", ["Unknown"])[0] if target_info.get("attributes") else "Unknown").lower()

    # Calculate Dominant Stat with Tie-Breaker (INT -> STR -> AGI)
    s, a, i = active.str_stat, active.agi_stat, active.int_stat
    
    # We want to pick the highest stat. On a tie, INT wins over STR, which wins over AGI.
    # We can do this by assigning a fractional priority value: INT > STR > AGI
    # INT: stat + 0.3
    # STR: stat + 0.2
    # AGI: stat + 0.1
    i_priority = i + 0.3
    s_priority = s + 0.2
    a_priority = a + 0.1
    
    if i_priority > s_priority and i_priority > a_priority:
        dominant = "int"
    elif s_priority > a_priority:
        dominant = "str"
    else:
        dominant = "agi"
        
    max_stat = max(s, a, i)
        
    # Hidden / Special Evolution Check (X-Antibody)
    if target_name.endswith(" X") or "X-Antibody" in target_name:
        if "X-Antibody" in inv.items and inv.items["X-Antibody"] > 0:
            if (s + a + i) >= (active.level * 3):
                return {"can_evolve": True, "reason": "X-Antibody Resonance Detected"}
            else:
                return {"can_evolve": False, "reason": "Stats too low for X-Mutation"}
        else:
            return {"can_evolve": False, "reason": "Requires X-Antibody Item"}
            
    # Crest Logic for specific branches
    if "Crest" in target_name or "Magnamon" in target_name or "Flamedramon" in target_name or "Raidramon" in target_name:
        if any("Courage" in c for c in inv.digimentals + inv.crests):
            # Check physical alignment matching lore
            if "Flamedramon" in target_name and dominant != "str":
                return {"can_evolve": False, "reason": "Requires STR Dominance"}
            if "Raidramon" in target_name and dominant != "agi":
                return {"can_evolve": False, "reason": "Requires AGI Dominance"}
            if "Magnamon" in target_name and dominant != "int":
                return {"can_evolve": False, "reason": "Requires INT Dominance"}
            return {"can_evolve": True, "reason": "Crest/Digimental Resonance Detected"}
        else:
            return {"can_evolve": False, "reason": "Requires Special Item"}

    # Base Level Requirements by Stage
    stage_reqs = {
        "baby ii": 3,
        "rookie": 10,
        "champion": 20,
        "ultimate": 40,
        "mega": 60,
        "ultra": 60
    }
    
    req_level = stage_reqs.get(target_stage_clean)
    if not req_level:
        # Fallback
        if active.level > 25: return {"can_evolve": True, "reason": "High Level Override"}
        return {"can_evolve": False, "reason": "Unknown Stage"}

    if active.level < req_level:
        return {"can_evolve": False, "reason": f"Requires Level {req_level}+"}
        
    # Baby II has no attribute branching
    if target_stage_clean == "baby ii":
        return {"can_evolve": True, "reason": "Level Requirement Met"}
        
    # Branching Logic (Rookie and above)
    if "vaccine" in target_attribute or "holy" in target_attribute or "light" in target_attribute:
        if dominant == "str" and active.bond >= 30:
            return {"can_evolve": True, "reason": "Vaccine Path Unlocked"}
        return {"can_evolve": False, "reason": "Req STR Dominant & Bond 30+"}
        
    elif "virus" in target_attribute or "dark" in target_attribute or "demon" in target_attribute:
        if dominant == "agi" and active.bond < 15:
            return {"can_evolve": True, "reason": "Virus Path Unlocked"}
        return {"can_evolve": False, "reason": "Req AGI Dominant & Bond < 15"}
        
    else: # Data / Default / Neutral
        if dominant == "int" and 15 <= active.bond <= 29:
            return {"can_evolve": True, "reason": "Data Path Unlocked"}
        return {"can_evolve": False, "reason": "Req INT Dominant & Bond 15-29"}


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

