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
            suggestions = planner.analyze_schedule()
            if not suggestions:
                return "Your schedule looks clear! No upcoming classes or deadlines detected in the immediate future."
                
            output = ["SMART STUDY ANALYSIS:"]
            for s in suggestions:
                output.append(f"Subject: {s['course']}")
                output.append(f"- Proactive Prep Time: {s['suggested_prep']}")
                if s["materials"]:
                    output.append("- Materials Found:")
                    for m in s["materials"]:
                        output.append(f"  * {m['title']}: {m['url']}")
                output.append(f"- Reasoning: {s['reason']}\n")
                
            return "\n".join(output)
        except Exception as e:
            return f"Error analyzing study schedule: {e}"
