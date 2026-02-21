import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/tasks', 'https://www.googleapis.com/auth/calendar']

class GoogleIntegration:
    def __init__(self):
        self.creds = None
        self.config_dir = os.path.expanduser('~/.digimon')
        os.makedirs(self.config_dir, exist_ok=True)
        self.token_pth = os.path.join(self.config_dir, 'token.json')
        self.credentials_pth = os.path.join(self.config_dir, 'credentials.json')

    def authenticate(self):
        if os.path.exists(self.token_pth):
            try:
                self.creds = Credentials.from_authorized_user_file(self.token_pth, SCOPES)
            except ValueError:
                self.creds = None
            
        if self.creds and self.creds.expired and self.creds.refresh_token:
            try:
                self.creds.refresh(Request())
                with open(self.token_pth, 'w') as token:
                    token.write(self.creds.to_json())
            except Exception as e:
                print(f"Error refreshing Google Token: {e}")
                self.creds = None
            
        if not self.creds or not self.creds.valid:
            print("Google API not authenticated. Please place credentials.json in ~/.digimon and run auth.")
            return False
            
        return True

    def get_tasks(self):
        if not self.authenticate():
            return []
            
        try:
            service = build('tasks', 'v1', credentials=self.creds, cache_discovery=False)
            results = service.tasklists().list(maxResults=10).execute()
            items = results.get('items', [])
            if not items:
                return []
                
            all_tasks = []
            for tasklist in items:
                tasklist_id = tasklist['id']
                tasks_result = service.tasks().list(tasklist=tasklist_id, showCompleted=False).execute()
                all_tasks.extend(tasks_result.get('items', []))
                
            return all_tasks
        except Exception as e:
            print(f"Error fetching Google Tasks: {e}")
            return []

    def complete_task(self, task_id: str) -> bool:
        if not self.authenticate():
            return False
            
        try:
            service = build('tasks', 'v1', credentials=self.creds, cache_discovery=False)
            results = service.tasklists().list(maxResults=10).execute()
            items = results.get('items', [])
            if not items:
                return False
                
            for tasklist in items:
                tasklist_id = tasklist['id']
                try:
                    # We might get a 404 if the task is not in this specific list,
                    # so we catch errors inside the loop.
                    task = service.tasks().get(tasklist=tasklist_id, task=task_id).execute()
                    task['status'] = 'completed'
                    service.tasks().update(tasklist=tasklist_id, task=task_id, body=task).execute()
                    return True
                except Exception:
                    continue # Not in this list, try the next one
                    
            print(f"Task {task_id} not found in any Google Tasks list.")
            return False
        except Exception as e:
            print(f"Error completing Google Task {task_id}: {e}")
            return False

    def create_task(self, title: str, due_date: str | None = None, notes: str | None = None) -> dict | None:
        """Create a new task in the first Google Tasks list.
        
        Args:
            title: Task title
            due_date: Optional due date in YYYY-MM-DD format
            notes: Optional task notes/description
        Returns:
            The created task dict, or None on failure
        """
        if not self.authenticate():
            return None
            
        try:
            service = build('tasks', 'v1', credentials=self.creds, cache_discovery=False)
            results = service.tasklists().list(maxResults=10).execute()
            items = results.get('items', [])
            if not items:
                return None
                
            tasklist_id = items[0]['id']
            body = {'title': title}
            if due_date:
                body['due'] = f'{due_date}T00:00:00.000Z'
            if notes:
                body['notes'] = notes
                
            task = service.tasks().insert(tasklist=tasklist_id, body=body).execute()
            return task
        except Exception as e:
            print(f"Error creating Google Task: {e}")
            return None

    def get_upcoming_events(self):
        if not self.authenticate():
            return []
            
        try:
            service = build('calendar', 'v3', credentials=self.creds, cache_discovery=False)
            import datetime
            now = datetime.datetime.utcnow().isoformat() + 'Z'
            events_result = service.events().list(calendarId='primary', timeMin=now,
                                                  maxResults=10, singleEvents=True,
                                                  orderBy='startTime').execute()
            return events_result.get('items', [])
        except Exception as e:
            print(f"Error fetching Google Calendar: {e}")
            return []
