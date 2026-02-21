import asyncio
from nanobot.game.notion_api import NotionIntegration
from nanobot.game.database import SessionLocal
from nanobot.game import models
from datetime import datetime, timezone

notion = NotionIntegration()
tasks = notion.fetch_mas_deadlines()
print(f"Fetched {len(tasks)} tasks")
for t in tasks:
    if not t["due_date"]: 
        continue
    try:
        due_str = t["due_date"]
        if len(due_str) == 10:
            due = datetime.strptime(due_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        else:
            due = datetime.fromisoformat(due_str.replace('Z', '+00:00'))
        
        now = datetime.now(timezone.utc)
        days_left = (due - now).days
        is_urgent = False
        if t["type"].lower() == "exam" and 0 <= days_left <= 7:
            is_urgent = True
        elif t["type"].lower() in ["assignment", "task"] and 0 <= days_left <= 3:
            is_urgent = True
            
        print(f"Task: {t['title']} | Type: {t['type']} | Due: {t['due_date']} (Days left: {days_left}) | Urgent: {is_urgent}")
        
    except Exception as e:
        print(f"Error parsing date {t['due_date']}: {e}")
