import os
import json
import datetime
from pathlib import Path
from .notion_api import NotionIntegration
from .google_api import GoogleIntegration

class StudyPlanner:
    def __init__(self):
        self.workspace_dir = Path(os.path.expanduser("~/.nanobot/workspace"))
        self.resources_file = self.workspace_dir / "study_resources.json"
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        
    def load_resources(self) -> dict:
        if self.resources_file.exists():
            with open(self.resources_file, "r") as f:
                return json.load(f)
        return {}
        
    def save_resources(self, resources: dict):
        with open(self.resources_file, "w") as f:
            json.dump(resources, f, indent=2)
            
    def sync_from_notion(self) -> dict:
        notion = NotionIntegration()
        new_resources = notion.fetch_study_materials()
        current = self.load_resources()
        current.update(new_resources)
        self.save_resources(current)
        return current

    def analyze_schedule(self) -> list:
        """Analyze calendar for upcoming classes and suggest prep windows."""
        google = GoogleIntegration()
        events = google.get_upcoming_events()
        resources = self.load_resources()
        
        suggestions = []
        now = datetime.datetime.utcnow()
        
        # Look for class patterns in the next 3 days
        for event in events:
            summary = event.get("summary", "").upper()
            start_str = event["start"].get("dateTime", event["start"].get("date"))
            # Simple ISO parse (naive)
            try:
                start_dt = datetime.datetime.fromisoformat(start_str.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                continue
                
            if start_dt < now:
                continue
                
            # Improved matching: Check for course code or substring
            is_class = False
            course_name = None
            
            summary_upper = summary.upper()
            for course in resources.keys():
                course_upper = course.upper()
                # If course code (e.g. MAS 121) is in summary
                # Extract first 7 chars often contains the code
                course_code = course_upper.split("-")[0].strip().split(":")[0].strip()
                
                if course_code in summary_upper or course_upper in summary_upper or summary_upper in course_upper:
                    is_class = True
                    course_name = course
                    break
            
            if "CLASS" in summary or "LECTURE" in summary:
                is_class = True
                
            if is_class:
                # Find a Prep Window: Suggest studying 24-48 hours before or a gap on the same day
                prep_time = start_dt - datetime.timedelta(hours=24)
                if prep_time < now:
                    prep_time = now + datetime.timedelta(hours=1)
                
                material_links = resources.get(course_name, []) if course_name else []
                
                suggestions.append({
                    "course": course_name or summary,
                    "class_time": start_dt.isoformat(),
                    "suggested_prep": prep_time.isoformat(),
                    "materials": material_links,
                    "reason": f"Proactive Prep: You have {course_name or summary} coming up. Let's sharpen your skills!"
                })
                
        return suggestions
