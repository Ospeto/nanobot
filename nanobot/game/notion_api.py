import os
import requests

def get_notion_key():
    key_path = os.path.expanduser("~/.config/notion/api_key")
    if os.path.exists(key_path):
        with open(key_path, "r") as f:
            return f.read().strip()
    return os.getenv("NOTION_API_KEY")

class NotionIntegration:
    def __init__(self):
        self.api_key = get_notion_key()
        self.headers = {
            "Authorization": f"Bearer {self.api_key}" if self.api_key else '',
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }
        
    def is_authenticated(self):
        return bool(self.api_key)

    def fetch_in_progress_tasks(self):
        if not self.is_authenticated():
            return []
            
        url = "https://api.notion.com/v1/search"
        payload = {"filter": {"value": "page", "property": "object"}}
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            results = response.json().get("results", [])
            tasks = []
            for r in results:
                props = r.get("properties", {})
                # Attempt to find a 'Status' property
                if "Status" in props:
                    status_obj = props["Status"].get("status") or props["Status"].get("select")
                    if status_obj and status_obj.get("name", "").lower() not in ["done", "completed"]:
                        tasks.append(r)
            return tasks
        except Exception as e:
            print(f"Error fetching Notion Tasks: {e}")
            return []
