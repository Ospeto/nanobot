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

    def fetch_mas_deadlines(self):
        if not self.is_authenticated():
            return []
            
        # Target MAS Assignments/Exams Database
        mas_db_id = "29a0cc17-6cb9-81e9-bc2e-d537a7cabb82"
        url = f"https://api.notion.com/v1/databases/{mas_db_id}/query"
        # Only fetch incomplete tasks
        payload = {
            "filter": {
                "property": "Status",
                "status": {
                    "does_not_equal": "Complete"
                }
            }
        }
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            results = response.json().get("results", [])
            tasks = []
            for r in results:
                props = r.get("properties", {})
                
                # Parse Title
                title_prop = props.get("Title", {}).get("title", [])
                title = title_prop[0].get("plain_text", "Untitled") if title_prop else "Untitled"
                
                # Parse Due Date
                due_date = None
                date_prop = props.get("Due Date", {}).get("date")
                if date_prop:
                    due_date = date_prop.get("start")
                    
                # Parse Type (Exam, Assignment, etc.)
                task_type = "Task"
                type_prop = props.get("Type", {}).get("select")
                if type_prop:
                    task_type = type_prop.get("name", "Task")
                    
                tasks.append({
                    "id": r["id"],
                    "title": title,
                    "due_date": due_date,
                    "type": task_type
                })
            return tasks
        except Exception as e:
            print(f"Error fetching MAS Deadlines: {e}")
            return []

    def complete_task(self, page_id: str) -> bool:
        if not self.is_authenticated():
            return False
            
        url = f"https://api.notion.com/v1/pages/{page_id}"
        payload = {
            "properties": {
                "Status": {
                    "status": {
                        "name": "Complete"
                    }
                }
            }
        }
        try:
            response = requests.patch(url, json=payload, headers=self.headers)
            if response.status_code != 200:
                # Try fallback for 'Done' or 'select' type property
                payload["properties"]["Status"] = {"status": {"name": "Done"}}
                response = requests.patch(url, json=payload, headers=self.headers)
                
            if response.status_code != 200:
                # Try fallback for select instead of status
                payload["properties"]["Status"] = {"select": {"name": "Complete"}}
                response = requests.patch(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Error completing Notion Task {page_id}: {e}")
            return False

    def create_assignment(self, title: str, due_date: str | None = None, task_type: str = "Assignment") -> dict | None:
        """Create a new assignment/exam entry in the MAS Dashboard Notion database.
        
        Args:
            title: Assignment/exam title
            due_date: Optional due date in YYYY-MM-DD format
            task_type: Type of task - 'Assignment', 'Exam', or 'Task'
        Returns:
            The created page dict, or None on failure
        """
        if not self.is_authenticated():
            return None
            
        mas_db_id = "29a0cc17-6cb9-81e9-bc2e-d537a7cabb82"
        url = "https://api.notion.com/v1/pages"
        
        properties = {
            "Title": {
                "title": [{"text": {"content": title}}]
            },
            "Status": {
                "status": {"name": "Not Started"}
            }
        }
        
        if task_type:
            properties["Type"] = {"select": {"name": task_type}}
            
        if due_date:
            properties["Due Date"] = {"date": {"start": due_date}}
        
        payload = {
            "parent": {"database_id": mas_db_id},
            "properties": properties
        }
        
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error creating Notion assignment: {e}")
            return None
