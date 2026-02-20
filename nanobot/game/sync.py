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
                    await self.sync_notion_tasks(db)
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
        google = GoogleIntegration()
        tasks = google.get_tasks()
        # TODO: Pass tasks to combat engine

    async def sync_notion_tasks(self, db: Session):
        notion = NotionIntegration()
        tasks = notion.fetch_in_progress_tasks()
        # TODO: Pass tasks to combat engine

    async def sync_calendar_events(self, db: Session):
        google = GoogleIntegration()
        events = google.get_upcoming_events()
        # TODO: Pass events to combat engine
