"""Game interaction tools for caring for the Digimon Partner."""

import json
from nanobot.agent.tools.base import Tool
try:
    from nanobot.game.database import SessionLocal
    from nanobot.game import state, shop
    from nanobot.game.draw_id_card import render_id_card
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
            "properties": {},
            "required": []
        }
        
    async def execute(self, source_filter: str | None = None, **kwargs) -> str:
        if not HAS_GAME:
            return "Game module not available."
        db = SessionLocal()
        try:
            from nanobot.game import models, sync
            
            # Initial check
            tasks = db.query(models.TaskSyncState).filter(
                models.TaskSyncState.status == "pending",
                models.TaskSyncState.source == "google_tasks"
            ).all()
            
            # If empty, try one immediate sync trigger
            if not tasks:
                sm = sync.SyncManager()
                await sm.sync_google_tasks(db)
                tasks = db.query(models.TaskSyncState).filter(
                    models.TaskSyncState.status == "pending",
                    models.TaskSyncState.source == "google_tasks"
                ).all()

            if not tasks:
                return "You have ZERO pending tasks! Good job! Tell the user they are completely clear."
                
            task_lines = [f"{i+1}. {t.title}" for i, t in enumerate(tasks)]
            
            output = "**Google Tasks:**\n" + "\n".join(f"- {t}" for t in task_lines)
            return f"PENDING TASKS:\n{output}\n\nTell the human they need to finish these to gain EXP and Food!"
        finally:
            db.close()


class CompleteTaskTool(Tool):
    @property
    def name(self) -> str:
        return "complete_task"
        
    @property
    def description(self) -> str:
        return "Mark a task as completed (deleted). Use the Exact ID from the list_tasks tool."
        
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "The EXACT ID of the task from the list_tasks tool output."
                },
                "source": {
                    "type": "string",
                    "description": "The exact source string ('google_tasks') for the task."
                }
            },
            "required": ["task_id", "source"]
        }
        
    async def execute(self, task_id: str, source: str, **kwargs) -> str:
        if not HAS_GAME:
            return "Game module not available."
        db = SessionLocal()
        try:
            from nanobot.game import models
            from nanobot.game.combat import Enemy, resolve_combat
            import logging
            
            logging.info(f"Attempting CompleteTaskTool with task_id={task_id}, source={source}")
            task = db.query(models.TaskSyncState).filter(models.TaskSyncState.id == task_id, models.TaskSyncState.source == source).first()
            if not task:
                logging.info(f"Task ID {task_id} not found in DB!")
                return f"Error: No pending {source} task with ID {task_id} found."
                
            success = False
            if source == "google_tasks":
                from nanobot.game.google_api import GoogleIntegration
                google = GoogleIntegration()
                success = google.complete_task(task_id)
                logging.info(f"Google API complete_task returned: {success}")
            else:
                return f"Unknown source (only google_tasks supported): {source}"
                
            if success:
                task.status = "completed"
                enemy = Enemy(task_source=source, task_id=task_id, title=task.title, status="completed")
                resolve_combat(db, enemy)
                db.commit()
                return f"Successfully completed/deleted the task '{task.title}'! You slayed this Dark Data!"
            else:
                return f"Failed to complete task '{task.title}'. API error occurred."
        except Exception as e:
            import logging
            logging.error(f"CompleteTaskTool exception: {e}")
            return f"Failed to complete task. Internal error: {str(e)}"
        finally:
            db.close()


class AddAssignmentTool(Tool):
    @property
    def name(self) -> str:
        return "add_assignment"
        
    @property
    def description(self) -> str:
        return "Add a new assignment or exam to both the MAS Notion Dashboard AND Google Tasks. Use when the Tamer tells you about a new assignment or exam."
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "The assignment/exam title, e.g. 'MAS 121 - Homework 3'"
                },
                "due_date": {
                    "type": "string",
                    "description": "Due date in YYYY-MM-DD format, e.g. '2026-03-15'. Optional."
                },
                "task_type": {
                    "type": "string",
                    "description": "Type: 'Assignment' or 'Exam'. Defaults to 'Assignment'.",
                    "enum": ["Assignment", "Exam"]
                }
            },
            "required": ["title"]
        }
    
    async def execute(self, title: str, due_date: str | None = None, task_type: str = "Assignment", **kwargs) -> str:
        if not HAS_GAME:
            return "Game module not available."
        
        results = []
        
        # 1. Create in Notion MAS Dashboard
        try:
            from nanobot.game.notion_api import NotionIntegration
            notion = NotionIntegration()
            notion_result = notion.create_assignment(title=title, due_date=due_date, task_type=task_type)
            if notion_result:
                results.append(f"✅ Added to Notion MAS Dashboard")
            else:
                results.append(f"❌ Failed to add to Notion")
        except Exception as e:
            results.append(f"❌ Notion error: {e}")
        
        # 2. Create in Google Tasks
        try:
            from nanobot.game.google_api import GoogleIntegration
            google = GoogleIntegration()
            google_result = google.create_task(title=title, due_date=due_date, notes=f"Type: {task_type}")
            if google_result:
                results.append(f"✅ Added to Google Tasks")
            else:
                results.append(f"❌ Failed to add to Google Tasks")
        except Exception as e:
            results.append(f"❌ Google Tasks error: {e}")
        
        status = "\n".join(results)
        return f"Assignment '{title}' (Due: {due_date or 'No date'}, Type: {task_type}):\n{status}\n\nTell the Tamer their assignment has been logged! Encourage them to start working on it!"
