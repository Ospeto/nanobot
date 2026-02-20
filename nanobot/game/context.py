from sqlalchemy.orm import Session
from . import state, memory, tiering

def build_system_prompt(db: Session, user_input: str) -> str:
    """
    Constructs the absolute state of the Agent for the LLM turn.
    """
    active_digimon = state.get_active_digimon(db)
    inventory = state.get_or_create_inventory(db)
    
    if not active_digimon:
        return "You are a standalone Nanobot without a Digimon Partner. Ask the user to run 'digimon init'."
        
    base_persona = tiering.get_system_prompt_for_stage(active_digimon.stage)
    
    status_str = ", ".join(active_digimon.status_effects) if active_digimon.status_effects else 'None'
    
    vitals = (
        f"--- CURRENT STATUS ---\n"
        f"Name: {active_digimon.name} ({active_digimon.species})\n"
        f"Stage: {active_digimon.stage} | Attribute: {active_digimon.attribute}\n"
        f"Level: {active_digimon.level} (EXP: {active_digimon.exp})\n"
        f"HP: {active_digimon.current_hp}/{active_digimon.max_hp}\n"
        f"Hunger: {active_digimon.hunger}/100 | Energy: {active_digimon.energy}/100\n"
        f"Status Effects: {status_str}\n"
    )
    
    inv = (
        f"--- INVENTORY ---\n"
        f"Bits: {inventory.bits}\n"
        f"Items: {inventory.items}\n"
        f"Crests: {inventory.crests}\n"
        f"Digi-Mentals: {inventory.digimentals}\n"
    )
    
    recent_memory = memory.get_memory_context_string(db, query=user_input)
    
    directives = (
        "--- SYSTEM DIRECTIVES ---\n"
        "1. Stay in character as the Digimon described above at all times.\n"
        "2. If your HP drops to 0, roleplay being extremely exhausted and beg for a Bandage or rest.\n"
        "3. Protect the user ('Tamer') from Dark Data (overdue tasks).\n"
        "4. Your capability to reason is bound by your evolutionary stage.\n"
    )
    
    return f"{base_persona}\n\n{vitals}\n{inv}\n{recent_memory}\n\n{directives}"
