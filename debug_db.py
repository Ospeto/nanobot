from nanobot.game.database import SessionLocal, DATABASE_URL
from nanobot.game.models import TaskSyncState
import os

print(f"DB URL: {DATABASE_URL}")
print(f"DB File Exists: {os.path.exists(DATABASE_URL.replace('sqlite:///', ''))}")

db = SessionLocal()
tasks = db.query(TaskSyncState).all()
print(f"All tasks count: {len(tasks)}")

google_tasks = db.query(TaskSyncState).filter_by(source='google_tasks', status='pending').all()
print(f"Pending Google tasks count: {len(google_tasks)}")

for t in google_tasks:
    print(f"- {t.title} (ID: {t.id})")

db.close()
