from typing import Any
from nanobot.agent.tools.base import Tool

class ListCalendarTool(Tool):
    @property
    def name(self) -> str:
        return "list_calendar"
        
    @property
    def description(self) -> str:
        return "List upcoming Google Calendar events to know the Tamer's schedule."
        
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
        
    async def execute(self, **kwargs) -> str:
        try:
            from nanobot.game.google_api import GoogleIntegration
            google = GoogleIntegration()
            events = google.get_upcoming_events()
            if not events:
                return "Your calendar is completely empty for the upcoming future."
                
            output = []
            for e in events:
                start = e['start'].get('dateTime', e['start'].get('date'))
                summary = e.get('summary', 'Unknown Event')
                id_ = e['id']
                output.append(f"- {start}: {summary} (ID: {id_})")
                
            return "UPCOMING CALENDAR EVENTS:\n" + "\n".join(output)
        except Exception as e:
            return f"Error listing calendar events: {e}"

class BlockTimeTool(Tool):
    @property
    def name(self) -> str:
        return "block_time"
        
    @property
    def description(self) -> str:
        return "Aggressively block time on Google Calendar for a specific task. Forces the Tamer to focus."
        
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Title of the calendar block (e.g. 'FOCUS: Complete Math Homework')."
                },
                "start_time": {
                    "type": "string",
                    "description": "ISO format string for start time (e.g. '2026-02-21T18:00:00Z')."
                },
                "end_time": {
                    "type": "string",
                    "description": "ISO format string for end time (e.g. '2026-02-21T19:00:00Z')."
                },
                "task_id": {
                    "type": "string",
                    "description": "The EXACT Google Task ID this block corresponds to. Will be put in the description."
                }
            },
            "required": ["summary", "start_time", "end_time"]
        }
        
    async def execute(self, summary: str, start_time: str, end_time: str, task_id: str = None, **kwargs) -> str:
        try:
            from nanobot.game.google_api import GoogleIntegration
            desc = f"Combat Zone for Task: {task_id}" if task_id else "Combat Zone!"
            google = GoogleIntegration()
            
            # Check freebusy (optional enforcement, but here we just blindly block it if Tamer agrees)
            event = google.create_event(summary=summary, start_time=start_time, end_time=end_time, description=desc)
            if event:
                return f"SUCCESS: Aggressively blocked '{summary}' on the calendar from {start_time} to {end_time}. Tell the Tamer to prepare for combat!"
            return "Failed to block time. Calendar API error."
        except Exception as e:
            return f"Error blocking time: {e}"

class ManageCalendarTool(Tool):
    @property
    def name(self) -> str:
        return "manage_calendar"
        
    @property
    def description(self) -> str:
        return "Update or Delete an existing calendar event. Only do this if the Tamer literally cannot fight the Dark Data at the scheduled time."
        
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["update", "delete"],
                    "description": "Action to perform."
                },
                "event_id": {
                    "type": "string",
                    "description": "The Calendar Event ID."
                },
                "new_start_time": {
                    "type": "string",
                    "description": "For update: ISO start time."
                },
                "new_end_time": {
                    "type": "string",
                    "description": "For update: ISO end time."
                }
            },
            "required": ["action", "event_id"]
        }
        
    async def execute(self, action: str, event_id: str, new_start_time: str = None, new_end_time: str = None, **kwargs) -> str:
        try:
            from nanobot.game.google_api import GoogleIntegration
            google = GoogleIntegration()
            
            if action == 'delete':
                if google.delete_event(event_id):
                    return f"Event {event_id} deleted. The block is cleared."
                return "Failed to delete event."
            elif action == 'update':
                updated = google.update_event(event_id=event_id, start_time=new_start_time, end_time=new_end_time)
                if updated:
                    return f"Event {event_id} rescheduled. Don't let the Tamer retreat next time!"
                return "Failed to update event."
            return "Unknown action."
        except Exception as e:
            return f"Error managing calendar: {e}"
