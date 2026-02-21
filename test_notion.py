from nanobot.game.notion_api import NotionIntegration

n = NotionIntegration()
try:
    print("Trying task complete...")
    tasks = n.fetch_in_progress_tasks()
    if tasks:
        t_id = tasks[0]['id']
        print(f"Testing completion on: {t_id}")
        res = n.complete_task(t_id)
        print("Success?", res)
    else:
        print("No tasks found.")
except Exception as e:
    print("Caught:", e)
