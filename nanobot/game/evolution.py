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

async def check_evolution_ready(db: Session) -> dict:
    digi = state.get_active_digimon(db)
    if not digi:
        return {"error": "No active digimon"}
        
    info = await Digipedia.get_digimon_info(digi.name)
    if not info:
        return {"error": "Could not fetch evolution data"}
        
    next_evos = info.get("evolvesTo", [])
    possible = []
    
    inv = state.get_or_create_inventory(db)
    crests = inv.crests if inv.crests else []
    digimentals = inv.digimentals if inv.digimentals else []
    
    for evo in next_evos:
        target_name = evo.get("name")
        if not target_name:
            continue
            
        # Strongly prefer canon evolutions according to the Digimon DB dataset
        if not evo.get("canon"):
            continue
            
        # Optional check: If we have specific item requirements later, we can read them from 'condition'
        # but the local DB mostly relies on raw possible targets. We keep crests logic loosely coupled.
        
        # Stage filtering: Ensure logical progression
        # e.g., Baby I -> Baby II, Baby II -> Rookie, etc.
        target_info = await Digipedia.get_digimon_info(target_name)
        if target_info:
            # Data structure: levels is list of str, level is str
            target_level_list = target_info.get("levels", [])
            target_level_str = target_level_list[0] if target_level_list else target_info.get("level", "")
            
            current_stage = str(digi.stage or "").lower()
            target_stage = str(target_level_str or "").lower()
            
            # Mapping API terms to Internal terms
            api_to_internal = {
                "child": "rookie",
                "adult": "champion",
                "perfect": "ultimate",
                "ultimate": "mega"
            }
            target_stage = api_to_internal.get(target_stage, target_stage)

            # Simple linear progression check
            stage_order = ["baby i", "baby ii", "rookie", "champion", "ultimate", "mega", "ultra"]
            try:
                curr_idx = stage_order.index(current_stage)
                target_idx = stage_order.index(target_stage)
                if target_idx != curr_idx + 1:
                    continue # Skip skips or side-grades for now
            except ValueError:
                # If stage not in our list, fallback to inclusion
                pass

        # Mock bond check to prevent immediate evolution parsing explosion
        if digi.bond >= 50 or digi.level >= 10:
            possible.append(target_name)
            
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

