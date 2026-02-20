"""Game interaction tools for caring for the Digimon Partner."""

import json
from nanobot.agent.tools.base import Tool
try:
    from nanobot.game.database import SessionLocal
    from nanobot.game import state, shop
    HAS_GAME = True
except ImportError:
    HAS_GAME = False

class FeedTool(Tool):
    @property
    def name(self) -> str:
        return "feed_digimon"
        
    @property
    def description(self) -> str:
        return "Feed your Digimon an item from the shop (e.g. 'Meat' or 'Sirloin') to restore its Hunger and Energy. This uses Bits."
        
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "food_item": {
                    "type": "string",
                    "enum": ["Meat", "Sirloin"],
                    "description": "The type of food to buy and feed the Digimon."
                }
            },
            "required": ["food_item"]
        }
        
    async def execute(self, food_item: str, **kwargs) -> str:
        if not HAS_GAME:
            return "Game module not available."
        db = SessionLocal()
        try:
            # Check bits and buy item
            res = shop.buy_item(db, food_item)
            if "error" in res:
                return f"Failed to feed: {res['error']}. Check your Bits!"
                
            # Apply effect
            digi = state.get_active_digimon(db)
            if not digi:
                return "You don't have an active Digimon Partner."
                
            effect = shop.SHOP_CATALOG[food_item]["effect"]
            if "hunger" in effect:
                digi.hunger = min(100, digi.hunger + effect["hunger"])
            digi.energy = min(100, digi.energy + effect.get("energy", 10))
            db.commit()
            return f"Successfully fed {food_item} to {digi.name}! Hunger is now {digi.hunger}/100 and Energy is {digi.energy}/100."
        finally:
            db.close()


class HealTool(Tool):
    @property
    def name(self) -> str:
        return "heal_digimon"

    @property
    def description(self) -> str:
        return "Heal your Digimon using a Bandage. This cures sickness and restores HP. Uses Bits from your inventory."
        
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
        
    async def execute(self, **kwargs) -> str:
        if not HAS_GAME:
            return "Game module not available."
        db = SessionLocal()
        try:
            res = shop.buy_item(db, "Bandage")
            if "error" in res:
                return f"Failed to buy Bandage: {res['error']}"
                
            digi = state.get_active_digimon(db)
            if not digi:
                return "No active Digimon Partner."
                
            effect = shop.SHOP_CATALOG["Bandage"]["effect"]
            digi.current_hp = min(digi.max_hp, digi.current_hp + effect["hp"])
            if effect.get("cure_sick") and digi.status_effects:
                status = list(digi.status_effects)
                if "Sick" in status:
                    status.remove("Sick")
                    digi.status_effects = status
            
            db.commit()
            return f"Successfully healed {digi.name}. HP is now {digi.current_hp}/{digi.max_hp}."
        finally:
            db.close()

class PlayTool(Tool):
    @property
    def name(self) -> str:
        return "play_with_digimon"
        
    @property
    def description(self) -> str:
        return "Play a game with your Digimon to increase Bond and decrease Energy/Hunger. (Costs nothing but time)"
        
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
        
    async def execute(self, **kwargs) -> str:
        if not HAS_GAME:
            return "Game module not available."
        db = SessionLocal()
        try:
            digi = state.get_active_digimon(db)
            if not digi:
                return "No active Digimon Partner."
            
            if digi.energy < 20 or digi.hunger < 20:
                return f"{digi.name} is too exhausted/hungry to play right now!"
                
            digi.bond = min(100, digi.bond + 5)
            digi.energy -= 10
            digi.hunger -= 10
            db.commit()
            
            return f"You played with {digi.name}! Bond increased to {digi.bond}. Energy is now {digi.energy}/100 and Hunger is {digi.hunger}/100."
        finally:
            db.close()

class ListTasksTool(Tool):
    @property
    def name(self) -> str:
        return "list_tasks"
        
    @property
    def description(self) -> str:
        return "List all pending tasks synchronized from Google Tasks or Notion. This tells you what the human needs to complete, so your Digimon character can aggressively encourage them to do it."
        
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "source_filter": {
                    "type": "string",
                    "description": "Optional: Filter by 'notion' or 'google_tasks'. Leave empty to get all tasks."
                }
            },
            "required": []
        }
        
    async def execute(self, source_filter: str | None = None, **kwargs) -> str:
        if not HAS_GAME:
            return "Game module not available."
        db = SessionLocal()
        try:
            from nanobot.game import models
            query = db.query(models.TaskSyncState).filter(models.TaskSyncState.status == "pending")
            if source_filter:
                query = query.filter(models.TaskSyncState.source == source_filter)
            
            tasks = query.all()
            if not tasks:
                return f"You have ZERO pending tasks{' for ' + source_filter if source_filter else ''}! Good job! Tell the user they are completely clear."
                
            notion_tasks = [t.title for t in tasks if t.source == 'notion']
            google_tasks = [t.title for t in tasks if t.source == 'google_tasks']
            
            output = []
            if notion_tasks:
                output.append(f"**Notion Tasks:**\n" + "\n".join(f"- {t}" for t in notion_tasks))
            if google_tasks:
                output.append(f"**Google Tasks:**\n" + "\n".join(f"- {t}" for t in google_tasks))
            
            task_list = "\n\n".join(output)
            return f"PENDING TASKS:\n{task_list}\n\nTell the human they need to finish these to gain EXP and Food!"
        finally:
            db.close()
