import os
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from .database import SessionLocal
from . import models, state
from .google_api import GoogleIntegration
from .notion_api import NotionIntegration

class SyncManager:
    def __init__(self):
        self.last_sync = datetime.utcnow()
        
    async def run_sync_loop(self):
        print("Starting SyncManager Background Loop...")
        while True:
            try:
                db = SessionLocal()
                try:
                    self.process_vital_decay(db)
                    await self.sync_google_tasks(db)
                    await self.sync_calendar_events(db)
                finally:
                    db.close()
                await asyncio.sleep(60) # 1 minute tick
            except asyncio.CancelledError:
                print("SyncManager Loop Cancelled.")
                break
            except Exception as e:
                print(f"SyncManager Error: {e}")
                await asyncio.sleep(60)

    def process_vital_decay(self, db: Session):
        now = datetime.utcnow()
        active = state.get_active_digimon(db)
        if not active:
            return
            
        try:
            last_updated = datetime.fromisoformat(active.last_updated)
        except ValueError:
            last_updated = now
            active.last_updated = now.isoformat()
            db.commit()
            
        time_since_last_decay = (now - last_updated).total_seconds()
        
        # Every 60 minutes, decrease Hunger by 2 and Energy by 1
        if time_since_last_decay > 3600:
            active.hunger = max(0, active.hunger - 2)
            active.energy = max(0, active.energy - 1)
            
            # HP penalty if starving
            if active.hunger == 0:
                active.current_hp = max(0, active.current_hp - 5)
                active.care_mistakes += 1
                
            active.last_updated = now.isoformat()
            db.commit()

    async def sync_google_tasks(self, db: Session):
        from .combat import Enemy, resolve_combat
        google = GoogleIntegration()
        if not google.authenticate():
            return
        tasks = google.get_tasks()
        
        existing = db.query(models.TaskSyncState).filter(
            models.TaskSyncState.source == "google_tasks"
        ).all()
        
        current_ids = {t.get("id"): t for t in tasks if t.get("id")}
        existing_ids = {ex.id: ex for ex in existing}
        
        for ex in existing:
            if ex.id not in current_ids and ex.status == "pending":
                ex.status = "completed"
                enemy = Enemy(task_source="google_tasks", task_id=ex.id, title=ex.title, status="completed")
                resolve_combat(db, enemy)
                
        for t_id, t_data in current_ids.items():
            if t_id not in existing_ids:
                new_task = models.TaskSyncState(
                    id=t_id,
                    source="google_tasks",
                    title=t_data.get("title", "Untitled Task"),
                    status="pending",
                    attribute=Enemy("google_tasks", t_id, t_data.get("title", ""), "pending").attribute
                )
                db.add(new_task)
            elif existing_ids[t_id].status != "pending":
                existing_ids[t_id].status = "pending"
        
        try:
            db.commit()
        except Exception:
            db.rollback()



    async def sync_calendar_events(self, db: Session):
        from .combat import Enemy, resolve_combat
        google = GoogleIntegration()
        if not google.authenticate():
            return
        events = google.get_upcoming_events()
        # Mock logic to avoid too much complexity:
        # Just ensure events don't break the system, we can skip full combat tracking for events for now.
        pass
