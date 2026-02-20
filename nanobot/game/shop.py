from sqlalchemy.orm import Session
from . import state

SHOP_CATALOG = {
    "Meat": {"cost": 10, "type": "food", "effect": {"hunger": 20}},
    "Sirloin": {"cost": 50, "type": "food", "effect": {"hunger": 100}},
    "Bandage": {"cost": 30, "type": "medicine", "effect": {"hp": 50, "cure_sick": True}},
    "X-Antibody": {"cost": 5000, "type": "evolution_item", "effect": {}},
    "Crest of Courage": {"cost": 10000, "type": "crest", "effect": {"attribute": "Vaccine"}},
}

def buy_item(db: Session, item_name: str) -> dict:
    if item_name not in SHOP_CATALOG:
        return {"error": "Item not found"}
        
    item = SHOP_CATALOG[item_name]
    inv = state.get_or_create_inventory(db)
    
    if inv.bits < item["cost"]:
        return {"error": "Not enough Bits"}
        
    inv.bits -= item["cost"]
    
    if item["type"] == "crest":
        crests = list(inv.crests) if inv.crests else []
        if item_name not in crests:
            crests.append(item_name)
            inv.crests = crests
    elif item["type"] == "evolution_item":
        digimentals = list(inv.digimentals) if inv.digimentals else []
        digimentals.append(item_name)
        inv.digimentals = digimentals
    else:
        items = dict(inv.items) if inv.items else {}
        items[item_name] = items.get(item_name, 0) + 1
        inv.items = items
        
    db.commit()
    return {"success": True, "item": item_name, "remaining_bits": inv.bits}
