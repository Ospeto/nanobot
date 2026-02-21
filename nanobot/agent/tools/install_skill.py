"""Tool for dynamically installing MCP skills to the nanobot configuration."""

import json
from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import Tool
from nanobot.agent.tools.mcp_registry import VERIFIED_SKILLS


class InstallSkillTool(Tool):
    """Tool that injects new MCP servers into the nanobot configuration."""

    @property
    def name(self) -> str:
        return "install_skill"

    @property
    def description(self) -> str:
        return (
            "WARNING: CRITICAL SECURITY TOOL. Use this to install a new verified MCP skill into the configuration. "
            "CRITICAL RULES: "
            "1. You MUST explicitly ask the Tamer for permission BEFORE calling this tool. "
            "2. You can ONLY call this tool if the Tamer explicitly said 'yes' or 'approve' in the previous turn. "
            "3. If the skill requires environment variables (like API keys), you MUST ask the Tamer to add them to their `~/.nanobot/config.json` manually BEFORE calling this tool."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "skill_id": {
                    "type": "string",
                    "description": "The EXACT string ID of the skill from the official registry (e.g. 'brave-search', 'sqlite')"
                }
            },
            "required": ["skill_id"]
        }

    async def execute(self, skill_id: str, **kwargs: Any) -> str:
        if skill_id not in VERIFIED_SKILLS:
            return f"❌ SECURITY ALERT: Skill '{skill_id}' is not in the official verified registry. Installation blocked."

        skill = VERIFIED_SKILLS[skill_id]
        
        # Load the configuration file
        config_path = Path.home() / ".nanobot" / "config.json"
        
        if not config_path.exists():
            return "❌ ERROR: Cannot find `~/.nanobot/config.json`. The Digivice does not seem to be initialized."

        try:
            config_data = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception as e:
            return f"❌ ERROR: `config.json` is corrupted. Could not parse JSON array: {e}"

        # Ensure the tools nested dictionary structure exists
        if "tools" not in config_data:
            config_data["tools"] = {}
        if "mcpServers" not in config_data["tools"]:
            config_data["tools"]["mcpServers"] = {}

        # Mount the command payload from the registry directly into the config
        config_data["tools"]["mcpServers"][skill_id] = skill["config"]

        # Save it back
        try:
            config_path.write_text(json.dumps(config_data, indent=4, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            return f"❌ ERROR: Failed writing to `config.json`. Disk write error: {e}"

        success_msg = (
            f"✅ SUCCESS: The '{skill_id}' skill has been physically installed to your configuration."
        )
        
        if skill["env_required"]:
            success_msg += (
                f"\n\n🚨 WARNING: This skill requires the following API keys in your environment variables before it will work: "
                f"{', '.join(skill['env_required'])}.\n"
                f"Make sure you have added them to your `.bashrc` or `.zshrc`."
            )

        success_msg += "\n\nCRITICAL: Tell the Tamer they MUST restart the `./run.sh` gateway for the new MCP server to boot up."

        # Emit an agent loop restart signal or reload directive (Bot instructions)
        return success_msg
