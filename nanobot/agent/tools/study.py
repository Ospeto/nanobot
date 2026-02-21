import json
from nanobot.agent.tools.base import Tool
from nanobot.game.study_logic import StudyPlanner

class SyncStudyResourcesTool(Tool):
    @property
    def name(self) -> str:
        return "sync_study_resources"
        
    @property
    def description(self) -> str:
        return "Sync study materials and class links from the MAS Notion database to the local cache."
        
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
            return f"SUCCESS: Synced {len(resources)} courses/subjects from Notion. Cache updated!"
        except Exception as e:
            return f"Error syncing study resources: {e}"

class AnalyzeStudyScheduleTool(Tool):
    @property
    def name(self) -> str:
        return "analyze_study_schedule"
        
    @property
    def description(self) -> str:
        return "Extremely smart analysis of Google Calendar and Notion deadlines to suggest the best study times and materials."
        
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
            # Auto-sync resources before analyzing
            planner.sync_from_notion()
            suggestions = planner.analyze_schedule()
            if not suggestions:
                return "Your schedule looks clear! No upcoming classes, assignments, or exams detected."
                
            output = ["🎓 SMART STUDY ANALYSIS (sorted by priority):"]
            for s in suggestions:
                urgency_icon = "🔴" if s.get("urgency") == "CRITICAL" else "🟡" if s.get("urgency") == "HIGH" else "🟢"
                output.append(f"\n{urgency_icon} [{s.get('urgency', '?')}] {s.get('type', '?')}: {s['course']}")
                output.append(f"  Due/Start: {s['class_time']} ({s.get('days_until', '?')} days)")
                output.append(f"  Suggested Prep: {s['suggested_prep']}")
                if s["materials"]:
                    output.append(f"  📚 {len(s['materials'])} study materials found:")
                    for m in s["materials"][:3]:  # Show top 3
                        output.append(f"    🔗 {m['title']}: {m['url']}")
                    if len(s["materials"]) > 3:
                        output.append(f"    ... and {len(s['materials']) - 3} more")
                output.append(f"  💡 {s['reason']}")
                
            return "\n".join(output)
        except Exception as e:
            return f"Error analyzing study schedule: {e}"
