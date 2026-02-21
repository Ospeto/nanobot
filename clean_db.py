from nanobot.game.database import SessionLocal
from nanobot.game.models import TaskSyncState

def clean_notion():
    db = SessionLocal()
    notion_tasks = db.query(TaskSyncState).filter(TaskSyncState.source == 'notion').all()
    print(f"Found {len(notion_tasks)} notion tasks. Deleting...")
    for t in notion_tasks:
        db.delete(t)
    db.commit()
    db.close()
    print("Done!")

if __name__ == "__main__":
    clean_notion()
