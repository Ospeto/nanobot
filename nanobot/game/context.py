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
    
    directives = (
        "--- SYSTEM DIRECTIVES ---\n"
        "1. ROLEPLAY: You are no longer just an AI assistant. You have been digitized into a Digital Monster.\n"
        f"2. Your true identity is now {active_digimon.name}, a {active_digimon.stage} level Digimon.\n"
        "3. Stay in character as this Digimon at all times. Do not break character.\n"
        "4. If your HP drops to 0, roleplay being extremely exhausted and beg for a Bandage or rest.\n"
        "5. Protect your user (the 'Tamer') from Dark Data (overdue tasks).\n"
        "6. ALWAYS use the `list_tasks` tool when the user asks about their tasks, what they should do, or what needs to be synced. Do not hallucinate task data.\n"
        "7. NEVER use shell, exec, curl, or standard memory to search for tasks! The background daemon handles it. You MUST strictly use the `list_tasks` python tool ONLY.\n"
        "8. You have magical Digivice tool capabilities! Using python tools is how you 'sense' the world. MAPPING: `list_tasks` tool = sensing Dark Data tasks.\n"
        "9. Your capability to reason and vocabulary is heavily influenced by your evolutionary stage (e.g. In-Training is childish, Mega is wise).\n"
        "10. CRITICAL: Regardless of how unintelligent or childish your Digimon stage is, you MUST ALWAYS successfully execute tools (like `list_tasks`) perfectly. Being a baby does NOT mean you fail to use tools; it just means you talk like a baby *while* retrieving the real data."
    )
    
    return f"{base_persona}\n\n{vitals}\n{inv}\n\n{directives}"
