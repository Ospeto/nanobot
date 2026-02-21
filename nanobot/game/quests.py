import random
from sqlalchemy.orm import Session
from nanobot.game import state

def roll_for_loot(db: Session, active, difficulty: str = "medium") -> dict:
    inv = state.get_or_create_inventory(db)
    
    # Base gains
    base_exp = 10 if difficulty == "hard" else 5
    active.exp += base_exp
    
    # Simplified leveling formula tracking total exp: level 1 is 0-9, level 2 is 10-19...
    old_level = active.level
    active.level = 1 + (active.exp // 10)  
    active.bond = min(100, active.bond + (5 if difficulty == "hard" else 2))
    
    # Loot roll (RNG)
    roll = random.random()
    dropped_item = None
    rarity = "none"
    
    # Simulated Drop Rates
    if difficulty == "hard": # e.g., Pomodoro training or boss fights
        if roll < 0.05: # 5% drop rate for Ultra-Rare
            dropped_item = "X-Antibody"
            rarity = "Ultra-Rare"
        elif roll < 0.25: # 20% drop rate for Rare
            crests = ["Crest of Courage", "Crest of Friendship", "Digimental of Courage", "Digimental of Miracles"]
            dropped_item = random.choice(crests)
            rarity = "Rare"
        elif roll < 0.70: # 45% drop rate for Consumables
            dropped_item = "Meat"
            rarity = "Common"
    else: # normal difficulty
        if roll < 0.10: # 10% for Consumables
            dropped_item = "Meat"
            rarity = "Common"
            
    if dropped_item:
        if "Crest" in dropped_item or "Digimental" in dropped_item:
            # Append safely to JSON array
            current_crests = list(inv.crests) if inv.crests else []
            if dropped_item not in current_crests:
                current_crests.append(dropped_item)
                inv.crests = current_crests
        else:
            # Append safely to JSON dict
            current_items = dict(inv.items) if inv.items else {}
            if dropped_item not in current_items:
                current_items[dropped_item] = 0
            current_items[dropped_item] += 1
            inv.items = current_items
            
    db.commit()
    
    msg = f"Gained +{base_exp} EXP!"
    if active.level > old_level:
        msg += f" {active.name} grew to Level {active.level}!"
    if dropped_item:
        msg += f"\nFound [{rarity}] {dropped_item}!"
        
    return {
        "success": True,
        "exp_gained": base_exp, 
        "new_level": active.level, 
        "dropped_item": dropped_item,
        "message": msg
    }
