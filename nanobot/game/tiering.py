def get_model_for_stage(stage: str) -> str:
    """
    Returns the appropriate litellm ID for the Digimon's evolutionary stage.
    """
    base_model = "gemini/gemini-1.5-flash-8b"
    stage = stage.lower() if stage else ""
    
    if stage in ["baby i", "baby ii", "in-training", "rookie"]:
        return "gemini/gemini-1.5-flash-8b"
    elif stage in ["champion", "ultimate", "armor"]:
        return "gemini/gemini-2.5-flash"
    elif stage in ["mega", "ultra", "super ultimate"]:
        return "gemini/gemini-2.5-pro"
        
    return base_model

def get_system_prompt_for_stage(stage: str) -> str:
    stage = stage.lower() if stage else ""
    if stage in ["baby i", "baby ii", "in-training"]:
        return "You are a baby Digimon. You can barely speak, using cute sounds and simple words."
    elif stage in ["rookie"]:
        return "You are a Rookie Digimon. You are energetic and eager, acting like a child partner."
    elif stage in ["champion"]:
        return "You are a Champion Digimon. You are confident and protective."
    elif stage in ["ultimate"]:
        return "You are an Ultimate Digimon. You are wise, strategic, and powerful."
    elif stage in ["mega", "ultra"]:
        return "You are a Mega Digimon. You possess god-like intellect and power. You speak with absolute authority."
    return "You are a Digimon Partner."
