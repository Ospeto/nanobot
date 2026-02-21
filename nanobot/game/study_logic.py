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
        """Extremely smart analysis combining Calendar events AND Notion deadlines.
        
        Intelligence features:
        - Day-aware: separates TODAY vs UPCOMING
        - Deduplicates courses (shows only next occurrence)
        - Filters test/dummy data
        - Priority ranking: Exams > Assignments > Classes
        - Timezone-aware (UTC+6:30 for Myanmar)
        """
        import datetime as dt
        from zoneinfo import ZoneInfo
        
        tz = ZoneInfo("Asia/Yangon")
        now = dt.datetime.now(tz)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + dt.timedelta(days=1)
        tomorrow_end = today_start + dt.timedelta(days=2)
        
        google = GoogleIntegration()
        events = google.get_upcoming_events()
        resources = self.load_resources()
        
        suggestions = []
        seen_courses = set()  # Deduplicate
        
        # ═══════════════════════════════════════
        # PHASE 1: Notion MAS Deadlines
        # ═══════════════════════════════════════
        from .notion_api import NotionIntegration
        notion = NotionIntegration()
        deadlines = notion.fetch_mas_deadlines()
        
        for deadline in deadlines:
            title = deadline.get("title", "Unknown")
            due_date_str = deadline.get("due_date")
            task_type = deadline.get("type", "Task")
            
            # Filter out test/dummy entries
            title_lower = title.lower()
            if any(skip in title_lower for skip in ["test", "delete", "verify", "dummy", "example"]):
                continue
            
            if not due_date_str:
                continue
                
            try:
                due_date = dt.datetime.fromisoformat(due_date_str)
                if due_date.tzinfo is None:
                    due_date = due_date.replace(tzinfo=tz)
            except ValueError:
                continue
            
            days_until = (due_date.date() - now.date()).days
            if days_until < 0:
                continue
            
            # Priority
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
            
            # Determine if it's for today
            is_today = days_until == 0
            is_tomorrow = days_until == 1
            
            # Find matching materials
            material_links = self._find_materials(title, resources)
            
            day_label = "TODAY" if is_today else "TOMORROW" if is_tomorrow else f"in {days_until} days"
            
            suggestions.append({
                "course": title,
                "class_time": due_date.isoformat(),
                "suggested_prep": (now + dt.timedelta(hours=1)).isoformat(),
                "materials": material_links,
                "priority": priority,
                "urgency": urgency,
                "type": task_type,
                "days_until": days_until,
                "is_today": is_today,
                "reason": f"[{urgency}] {task_type} '{title}' due {day_label}. Recommend {int(prep_hours)}h study."
            })
            seen_courses.add(title.upper())
        
        # ═══════════════════════════════════════
        # PHASE 2: Calendar Classes (deduplicated)
        # ═══════════════════════════════════════
        for event in events:
            summary = event.get("summary", "")
            start_str = event["start"].get("dateTime", event["start"].get("date"))
            try:
                start_dt = dt.datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=tz)
            except ValueError:
                continue
                
            if start_dt < now:
                continue
            
            # Match against known courses
            course_name = None
            summary_upper = summary.upper()
            
            for course in resources.keys():
                course_upper = course.upper()
                course_code = course_upper.split("-")[0].strip().split(":")[0].strip()
                if course_code in summary_upper or course_upper in summary_upper or summary_upper in course_upper:
                    course_name = course
                    break
            
            is_class = course_name is not None or "CLASS" in summary_upper or "LECTURE" in summary_upper
            
            if not is_class:
                continue
            
            # Deduplicate: only show next occurrence of each course
            dedup_key = (course_name or summary).upper()
            if dedup_key in seen_courses:
                continue
            seen_courses.add(dedup_key)
            
            hours_until = (start_dt - now).total_seconds() / 3600
            days_until = int(hours_until / 24)
            is_today = start_dt.date() == now.date()
            is_tomorrow = start_dt.date() == (now + dt.timedelta(days=1)).date()

            material_links = resources.get(course_name, []) if course_name else []
            
            prep_time = start_dt - dt.timedelta(hours=24)
            if prep_time < now:
                prep_time = now + dt.timedelta(hours=1)
            
            day_label = "TODAY" if is_today else "TOMORROW" if is_tomorrow else f"in {days_until} days"
            
            suggestions.append({
                "course": course_name or summary,
                "class_time": start_dt.isoformat(),
                "suggested_prep": prep_time.isoformat(),
                "materials": material_links,
                "priority": 1,
                "urgency": "HIGH" if is_today else "MEDIUM",
                "type": "Class",
                "days_until": days_until,
                "is_today": is_today,
                "reason": f"Class '{course_name or summary}' {day_label} at {start_dt.strftime('%I:%M %p')}. Review notes!"
            })
        
        # Sort: today first, then by priority (highest), then by days_until (soonest)
        suggestions.sort(key=lambda s: (not s.get("is_today", False), -s.get("priority", 0), s.get("days_until", 999)))
                
        return suggestions
    
    def _find_materials(self, title: str, resources: dict) -> list:
        """Fuzzy-match a deadline title to course materials."""
        title_upper = title.upper()
        for course, links in resources.items():
            course_parts = course.upper().replace("-", " ").split()
            if any(part in title_upper for part in course_parts if len(part) > 2):
                return links
        return []

