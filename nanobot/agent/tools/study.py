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
            planner = StudyPlanner()
            planner.sync_from_notion()
            suggestions = planner.analyze_schedule()
            
            # Also check for missing data
            from nanobot.game.notion_api import NotionIntegration
            notion = NotionIntegration()
            courses = notion.fetch_course_metadata()
            
            # Build output
            output = []
            
            # Active courses summary
            active = [c for c in courses if c["status"] == "In Progress"]
            completed = [c for c in courses if c["status"] in ("Completed", "Complete")]
            output.append(f"📊 COURSE STATUS: {len(active)} active, {len(completed)} completed")
            output.append(f"Active courses: {', '.join(c['name'] for c in active)}")
            
            # Study suggestions
            if suggestions:
                output.append(f"\n🎓 STUDY SCHEDULE ({len(suggestions)} items):")
                for s in suggestions:
                    today_marker = " ⭐TODAY" if s.get("is_today") else ""
                    urgency_icon = "🔴" if s.get("urgency") == "CRITICAL" else "🟡" if s.get("urgency") == "HIGH" else "🟢"
                    output.append(f"\n{urgency_icon} [{s.get('urgency')}] {s.get('type')}: {s['course']}{today_marker}")
                    output.append(f"  Due: {s['class_time']} ({s.get('days_until', '?')} days)")
                    if s["materials"]:
                        output.append(f"  📚 {len(s['materials'])} study materials available")
                    output.append(f"  💡 {s['reason']}")
            else:
                output.append("\n✅ No urgent deadlines or classes detected for active courses.")
            
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
                output.append("\n📋 MISSING DATA (ask Tamer to fill these in Notion or tell you):")
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

