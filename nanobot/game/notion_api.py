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

    def fetch_study_materials(self) -> dict:
        """Fetch study materials ONLY for active (In Progress) courses."""
        if not self.is_authenticated():
            return {}
            
        resources = {}
        course_id_to_name = {}
        
        # 1. Fetch active courses only
        course_db_id = "29a0cc17-6cb9-817d-856a-d76eaae22769"
        url = f"https://api.notion.com/v1/databases/{course_db_id}/query"
        # Filter: only "In Progress" courses
        payload = {
            "filter": {
                "property": "Status",
                "status": {
                    "equals": "In Progress"
                }
            }
        }
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            for r in response.json().get("results", []):
                props = r.get("properties", {})
                name_prop = props.get("Name", {}).get("title", [])
                name = name_prop[0].get("plain_text") if name_prop else "Unknown Course"
                course_id_to_name[r["id"]] = name
                
                # Check Syllabus (Files)
                files = props.get("Syllabus", {}).get("files", [])
                for f in files:
                    file_url = f.get("file", {}).get("url") or f.get("external", {}).get("url")
                    if file_url:
                        if name not in resources: resources[name] = []
                        resources[name].append({"title": f.get("name", "Syllabus"), "url": file_url})
        except Exception as e:
            print(f"Error fetching Course resources: {e}")

        # 2. Fetch Notes linked to active courses
        notes_db_id = "29a0cc17-6cb9-81f0-8243-eeba9a314ea7"
        url = f"https://api.notion.com/v1/databases/{notes_db_id}/query"
        try:
            response = requests.post(url, json={}, headers=self.headers)
            response.raise_for_status()
            for r in response.json().get("results", []):
                props = r.get("properties", {})
                name_prop = props.get("Name", {}).get("title", [])
                note_name = name_prop[0].get("plain_text") if name_prop else "Note"
                note_url = r.get("url")
                
                course_rels = props.get("Course", {}).get("relation", [])
                for rel in course_rels:
                    course_id = rel.get("id")
                    course_name = course_id_to_name.get(course_id)
                    if course_name:
                        if course_name not in resources: resources[course_name] = []
                        if not any(l["url"] == note_url for l in resources[course_name]):
                            resources[course_name].append({"title": f"Note: {note_name}", "url": note_url})
        except Exception as e:
            print(f"Error fetching Notes resources: {e}")
            
        return resources

    def fetch_course_metadata(self) -> list[dict]:
        """Fetch detailed metadata for all courses to identify gaps."""
        if not self.is_authenticated():
            return []
            
        course_db_id = "29a0cc17-6cb9-817d-856a-d76eaae22769"
        url = f"https://api.notion.com/v1/databases/{course_db_id}/query"
        courses = []
        try:
            response = requests.post(url, json={}, headers=self.headers)
            response.raise_for_status()
            for r in response.json().get("results", []):
                props = r.get("properties", {})
                name_prop = props.get("Name", {}).get("title", [])
                name = name_prop[0].get("plain_text") if name_prop else "Unknown"
                
                # Status
                status_obj = props.get("Status", {})
                if status_obj.get("type") == "status":
                    status = status_obj.get("status", {}).get("name", "Unknown")
                else:
                    status = "Unknown"
                
                # Quarter
                quarter_obj = props.get("Quarter", {})
                quarter = None
                if quarter_obj.get("type") == "select" and quarter_obj.get("select"):
                    quarter = quarter_obj["select"].get("name")
                
                # Professor
                prof_obj = props.get("Professor", {})
                professor = None
                if prof_obj.get("type") == "rich_text":
                    texts = prof_obj.get("rich_text", [])
                    if texts:
                        professor = texts[0].get("plain_text")
                
                # Syllabus
                has_syllabus = bool(props.get("Syllabus", {}).get("files", []))
                
                # Schedule
                schedule_obj = props.get("Schedule", {})
                schedule = None
                if schedule_obj.get("type") == "rich_text":
                    texts = schedule_obj.get("rich_text", [])
                    if texts:
                        schedule = texts[0].get("plain_text")
                
                courses.append({
                    "id": r["id"],
                    "name": name,
                    "status": status,
                    "quarter": quarter,
                    "professor": professor,
                    "has_syllabus": has_syllabus,
                    "schedule": schedule,
                    "url": r.get("url"),
                })
        except Exception as e:
            print(f"Error fetching course metadata: {e}")
        
        return courses

    def update_course_property(self, page_id: str, property_name: str, value: str) -> bool:
        """Update a text property on a Notion Course page."""
        if not self.is_authenticated():
            return False
        
        url = f"https://api.notion.com/v1/pages/{page_id}"
        payload = {
            "properties": {
                property_name: {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": value}
                        }
                    ]
                }
            }
        }
        try:
            response = requests.patch(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Error updating course property: {e}")
            return False
