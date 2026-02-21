import json
from nanobot.agent.tools.base import Tool
from nanobot.game.study_logic import StudyPlanner

class SyncStudyResourcesTool(Tool):
    @property
    def name(self) -> str:
        return "sync_study_resources"
        
    @property
    def description(self) -> str:
        return "Sync study materials from ACTIVE (In Progress) MAS Notion courses to the local cache."
        
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
        
    async def execute(self, **kwargs) -> str:
        try:
            planner = StudyPlanner()
            resources = planner.sync_from_notion()
            return f"SUCCESS: Synced {len(resources)} ACTIVE courses from Notion (completed courses filtered out). Cache updated!"
        except Exception as e:
            return f"Error syncing study resources: {e}"

class AnalyzeStudyScheduleTool(Tool):
    @property
    def name(self) -> str:
        return "analyze_study_schedule"
        
    @property
    def description(self) -> str:
        return "Smart analysis of upcoming deadlines and classes. Only considers ACTIVE courses (In Progress). Identifies missing data fields."
        
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
        
    async def execute(self, **kwargs) -> str:
        try:
            import datetime as dt
            from zoneinfo import ZoneInfo
            
            tz = ZoneInfo("Asia/Yangon")
            now = dt.datetime.now(tz)
            day_name = now.strftime("%A")  # e.g., "Sunday"
            date_str = now.strftime("%B %d, %Y")  # e.g., "February 22, 2026"
            time_str = now.strftime("%I:%M %p")  # e.g., "12:41 AM"
            
            planner = StudyPlanner()
            planner.sync_from_notion()
            suggestions = planner.analyze_schedule()
            
            # Also check for missing data
            from nanobot.game.notion_api import NotionIntegration
            notion = NotionIntegration()
            courses = notion.fetch_course_metadata()
            
            # Build output
            output = []
            
            # TIME CONTEXT (most important!)
            output.append(f"🕐 CURRENT TIME: {day_name}, {date_str} at {time_str} (Myanmar Time)")
            
            # Active courses summary
            active = [c for c in courses if c["status"] == "In Progress"]
            completed = [c for c in courses if c["status"] in ("Completed", "Complete")]
            output.append(f"📊 ACTIVE COURSES (2nd Quarter): {', '.join(c['name'] for c in active)}")
            output.append(f"   ({len(completed)} first-quarter courses completed and filtered out)")
            
            # Study suggestions
            today_items = [s for s in suggestions if s.get("is_today")]
            upcoming_items = [s for s in suggestions if not s.get("is_today")]
            
            if today_items:
                output.append(f"\n⭐ TODAY ({day_name}):")
                for s in today_items:
                    urgency_icon = "🔴" if s.get("urgency") == "CRITICAL" else "🟡" if s.get("urgency") == "HIGH" else "🟢"
                    output.append(f"  {urgency_icon} {s.get('type')}: {s['course']}")
                    output.append(f"     Time: {s['class_time']}")
                    if s["materials"]:
                        output.append(f"     📚 {len(s['materials'])} study materials available")
                    output.append(f"     💡 {s['reason']}")
            else:
                output.append(f"\n✅ No classes or deadlines TODAY ({day_name}). You're free!")
            
            if upcoming_items:
                output.append(f"\n📅 UPCOMING:")
                for s in upcoming_items:
                    urgency_icon = "🔴" if s.get("urgency") == "CRITICAL" else "🟡" if s.get("urgency") == "HIGH" else "🟢"
                    output.append(f"  {urgency_icon} {s.get('type')}: {s['course']} (in {s.get('days_until')} days)")
                    output.append(f"     💡 {s['reason']}")
            
            # Missing data report
            gaps = []
            for c in active:
                missing = []
                if not c.get("professor"):
                    missing.append("Professor")
                if not c.get("has_syllabus"):
                    missing.append("Syllabus")
                if not c.get("schedule"):
                    missing.append("Schedule")
                if not c.get("quarter"):
                    missing.append("Quarter")
                if missing:
                    gaps.append(f"  ⚠️ {c['name']}: missing {', '.join(missing)}")
            
            if gaps:
                output.append("\n📋 MISSING DATA (ask Tamer to fill these):")
                output.extend(gaps)
            
            return "\n".join(output)
        except Exception as e:
            return f"Error analyzing study schedule: {e}"


class IntrospectCoursesTool(Tool):
    @property
    def name(self) -> str:
        return "introspect_courses"
        
    @property
    def description(self) -> str:
        return "Deep inspection of all MAS courses in Notion. Shows status, quarter, professor, schedule, and identifies missing fields to ask the Tamer about."
        
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
        
    async def execute(self, **kwargs) -> str:
        try:
            from nanobot.game.notion_api import NotionIntegration
            notion = NotionIntegration()
            courses = notion.fetch_course_metadata()
            
            if not courses:
                return "No courses found in the MAS database."
            
            output = ["📚 MAS COURSE DATABASE INTROSPECTION:\n"]
            
            for c in courses:
                status_icon = "✅" if c["status"] in ("Completed", "Complete") else "📖" if c["status"] == "In Progress" else "⬜"
                output.append(f"{status_icon} {c['name']}")
                output.append(f"   Status: {c['status']} | Quarter: {c.get('quarter') or '❌ MISSING'}")
                output.append(f"   Professor: {c.get('professor') or '❌ MISSING'}")
                output.append(f"   Syllabus: {'✅' if c.get('has_syllabus') else '❌ MISSING'}")
                output.append(f"   Schedule: {c.get('schedule') or '❌ MISSING'}")
                output.append(f"   Notion: {c.get('url', 'N/A')}")
                output.append("")
            
            return "\n".join(output)
        except Exception as e:
            return f"Error introspecting courses: {e}"

class UpdateCourseFieldTool(Tool):
    @property
    def name(self) -> str:
        return "update_course_field"
        
    @property
    def description(self) -> str:
        return "Update a missing field on a MAS course in Notion. Use this when the Tamer tells you a missing piece of info (like schedule or professor name). First use introspect_courses to get the course ID."
        
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "course_name": {
                    "type": "string",
                    "description": "The course name to update (e.g., 'MAS 121 - Inferential Statistics')"
                },
                "field_name": {
                    "type": "string",
                    "description": "The field to update: 'Schedule' or 'Professor'",
                    "enum": ["Schedule", "Professor"]
                },
                "value": {
                    "type": "string",
                    "description": "The value to set (e.g., 'Mon & Thu 9:30-11:00 AM')"
                }
            },
            "required": ["course_name", "field_name", "value"]
        }
        
    async def execute(self, course_name: str = "", field_name: str = "", value: str = "", **kwargs) -> str:
        try:
            from nanobot.game.notion_api import NotionIntegration
            notion = NotionIntegration()
            courses = notion.fetch_course_metadata()
            
            # Find the course by name (fuzzy)
            target = None
            course_name_upper = course_name.upper()
            for c in courses:
                if c["name"].upper() in course_name_upper or course_name_upper in c["name"].upper():
                    target = c
                    break
                # Also try matching course code
                code = c["name"].upper().split("-")[0].strip()
                if code in course_name_upper:
                    target = c
                    break
            
            if not target:
                return f"Course '{course_name}' not found. Available: {', '.join(c['name'] for c in courses)}"
            
            success = notion.update_course_property(target["id"], field_name, value)
            if success:
                return f"SUCCESS: Updated '{field_name}' for {target['name']} to '{value}' in Notion!"
            else:
                return f"Failed to update Notion. Check API permissions."
        except Exception as e:
            return f"Error updating course field: {e}"
