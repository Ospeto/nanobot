import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from loguru import logger

SCOPES = ['https://www.googleapis.com/auth/tasks', 'https://www.googleapis.com/auth/calendar']

class GoogleIntegration:
    def __init__(self):
        self.creds = None
        self.config_dir = os.path.expanduser('~/.digimon')
        os.makedirs(self.config_dir, exist_ok=True)
        self.token_pth = os.path.join(self.config_dir, 'token.json')
        self.credentials_pth = os.path.join(self.config_dir, 'credentials.json')

    def authenticate(self, quiet: bool = False) -> bool:
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
                if not quiet:
                    print(f"Error refreshing Google Token: {e}")
                self.creds = None
            
        if not self.creds or not self.creds.valid:
            if not quiet:
                logger.warning("Google API not authenticated. Please run 'nanobot google-auth'.")
            return False
            
        return True

    def run_auth_flow(self):
        """Run the manual OAuth2 flow to generate token.json."""
        if not os.path.exists(self.credentials_pth):
            logger.error(f"Credentials not found at {self.credentials_pth}")
            return False
            
        flow = InstalledAppFlow.from_client_secrets_file(self.credentials_pth, SCOPES)
        self.creds = flow.run_local_server(port=0)
        
        with open(self.token_pth, 'w') as token:
            token.write(self.creds.to_json())
            
        logger.info(f"Authentication successful! Token saved to {self.token_pth}")
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
        # We pass quiet=True so the background loop doesn't spam logs every 60s
        if not self.authenticate(quiet=True):
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

    def create_event(self, summary: str, start_time: str, end_time: str, description: str = ''):
        if not self.authenticate():
            return None
            
        # Enforce timezone robustness for naive LLM outputs
        if len(start_time) > 10 and not start_time.endswith('Z') and '+' not in start_time and '-' not in start_time[10:]:
            start_time += 'Z'
        if len(end_time) > 10 and not end_time.endswith('Z') and '+' not in end_time and '-' not in end_time[10:]:
            end_time += 'Z'
            
        try:
            service = build('calendar', 'v3', credentials=self.creds, cache_discovery=False)
            event = {
                'summary': summary,
                'description': description,
                'start': {
                    'dateTime': start_time,
                },
                'end': {
                    'dateTime': end_time,
                }
            }
            event_result = service.events().insert(calendarId='primary', body=event).execute()
            return event_result
        except Exception as e:
            print(f"Error creating Calendar event: {e}")
            return None

    def find_freebusy(self, min_time: str, max_time: str):
        if not self.authenticate():
            return None
            
        try:
            service = build('calendar', 'v3', credentials=self.creds, cache_discovery=False)
            body = {
                "timeMin": min_time,
                "timeMax": max_time,
                "items": [{"id": "primary"}]
            }
            eventsResult = service.freebusy().query(body=body).execute()
            return eventsResult.get('calendars', {}).get('primary', {}).get('busy', [])
        except Exception as e:
            print(f"Error checking FreeBusy: {e}")
            return None

    def update_event(self, event_id: str, summary: str = None, start_time: str = None, end_time: str = None, description: str = None):
        if not self.authenticate():
            return None
            
        try:
            service = build('calendar', 'v3', credentials=self.creds, cache_discovery=False)
            event = service.events().get(calendarId='primary', eventId=event_id).execute()
            if summary is not None:
                event['summary'] = summary
            if description is not None:
                event['description'] = description
            if start_time is not None:
                if len(start_time) > 10 and not start_time.endswith('Z') and '+' not in start_time and '-' not in start_time[10:]:
                    start_time += 'Z'
                # Clear all-day date property if present, otherwise API throws 400 Bad Request
                if 'date' in event.get('start', {}):
                    event['start'].pop('date')
                event.setdefault('start', {})['dateTime'] = start_time
            if end_time is not None:
                if len(end_time) > 10 and not end_time.endswith('Z') and '+' not in end_time and '-' not in end_time[10:]:
                    end_time += 'Z'
                if 'date' in event.get('end', {}):
                    event['end'].pop('date')
                event.setdefault('end', {})['dateTime'] = end_time
                
            updated_event = service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
            return updated_event
        except Exception as e:
            print(f"Error updating Calendar event: {e}")
            return None

    def delete_event(self, event_id: str) -> bool:
        if not self.authenticate():
            return False
            
        try:
            service = build('calendar', 'v3', credentials=self.creds, cache_discovery=False)
            service.events().delete(calendarId='primary', eventId=event_id).execute()
            return True
        except Exception as e:
            print(f"Error deleting Calendar event {event_id}: {e}")
            return False
