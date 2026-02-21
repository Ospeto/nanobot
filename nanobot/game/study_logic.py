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
        """Extremely smart analysis combining Calendar events AND Notion deadlines."""
        google = GoogleIntegration()
        events = google.get_upcoming_events()
        resources = self.load_resources()
        
        suggestions = []
        now = datetime.datetime.utcnow()
        
        # ═══════════════════════════════════════
        # PHASE 1: Check Notion MAS deadlines (most reliable source)
        # ═══════════════════════════════════════
        from .notion_api import NotionIntegration
        notion = NotionIntegration()
        deadlines = notion.fetch_mas_deadlines()
        
        for deadline in deadlines:
            title = deadline.get("title", "Unknown")
            due_date_str = deadline.get("due_date")
            task_type = deadline.get("type", "Task")
            
            if not due_date_str:
                continue
                
            try:
                due_date = datetime.datetime.fromisoformat(due_date_str)
            except ValueError:
                continue
            
            days_until = (due_date - now).days
            if days_until < 0:
                continue  # Past due, skip
            
            # Priority multiplier: Exams need more prep than assignments
            if task_type.lower() == "exam":
                priority = 3
                prep_hours = min(48, max(4, days_until * 6))
                urgency = "CRITICAL" if days_until <= 3 else "HIGH"
            elif task_type.lower() == "assignment":
                priority = 2
                prep_hours = min(24, max(2, days_until * 3))
                urgency = "HIGH" if days_until <= 2 else "MEDIUM"
            else:
                priority = 1
                prep_hours = min(12, max(1, days_until * 2))
                urgency = "MEDIUM" if days_until <= 3 else "LOW"
            
            # Smart prep window: start studying earlier for harder tasks
            prep_time = now + datetime.timedelta(hours=1)
            
            # Find matching course materials
            material_links = []
            for course, links in resources.items():
                # Fuzzy match: check if any part of the course name appears in the deadline title
                course_parts = course.upper().replace("-", " ").split()
                title_upper = title.upper()
                if any(part in title_upper for part in course_parts if len(part) > 2):
                    material_links = links
                    break
            
            suggestions.append({
                "course": title,
                "class_time": due_date.isoformat(),
                "suggested_prep": prep_time.isoformat(),
                "materials": material_links,
                "priority": priority,
                "urgency": urgency,
                "type": task_type,
                "days_until": days_until,
                "reason": f"[{urgency}] {task_type} '{title}' is due in {days_until} day(s). I recommend {int(prep_hours)}h of focused study."
            })
        
        # ═══════════════════════════════════════
        # PHASE 2: Check Calendar for upcoming classes
        # ═══════════════════════════════════════
        for event in events:
            summary = event.get("summary", "")
            start_str = event["start"].get("dateTime", event["start"].get("date"))
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
                course_code = course_upper.split("-")[0].strip().split(":")[0].strip()
                if course_code in summary_upper or course_upper in summary_upper or summary_upper in course_upper:
                    is_class = True
                    course_name = course
                    break
            
            if "CLASS" in summary_upper or "LECTURE" in summary_upper:
                is_class = True
                
            if is_class:
                prep_time = start_dt - datetime.timedelta(hours=24)
                if prep_time < now:
                    prep_time = now + datetime.timedelta(hours=1)
                
                material_links = resources.get(course_name, []) if course_name else []
                hours_until = (start_dt - now).total_seconds() / 3600
                
                suggestions.append({
                    "course": course_name or summary,
                    "class_time": start_dt.isoformat(),
                    "suggested_prep": prep_time.isoformat(),
                    "materials": material_links,
                    "priority": 1,
                    "urgency": "HIGH" if hours_until < 24 else "MEDIUM",
                    "type": "Class",
                    "days_until": int(hours_until / 24),
                    "reason": f"Class '{course_name or summary}' in {int(hours_until)}h. Review your notes beforehand!"
                })
        
        # Sort by priority (highest first), then by days_until (soonest first)
        suggestions.sort(key=lambda s: (-s.get("priority", 0), s.get("days_until", 999)))
                
        return suggestions
