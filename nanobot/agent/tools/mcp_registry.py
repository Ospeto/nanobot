"""Tool for discovering verified MCP servers."""

import json
from typing import Any

from nanobot.agent.tools.base import Tool


# A hardcoded list of pre-verified, safe MCP servers.
# These mirror the exact configurations used by Claude Desktop.
VERIFIED_SKILLS = {
    "brave-search": {
        "description": "Brave Search API for querying the live internet.",
        "config": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-brave-search"]
        },
        "env_required": ["BRAVE_API_KEY"]
    },
    "sqlite": {
        "description": "Interact directly with local SQLite databases.",
        "config": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-sqlite"]
        },
        "env_required": []
    },
    "github": {
        "description": "Full access to GitHub API for managing repositories, issues, and pull requests.",
        "config": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"]
        },
        "env_required": ["GITHUB_PERSONAL_ACCESS_TOKEN"]
    },
    "puppeteer": {
        "description": "Browser automation toolkit for fetching raw HTML or taking screenshots of web pages.",
        "config": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-puppeteer"]
        },
        "env_required": []
    },
    "fetch": {
        "description": "Fetch website contents and convert to clean markdown.",
        "config": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-fetch"]
        },
        "env_required": []
    },
    "postgres": {
        "description": "Interact directly with PostgreSQL databases.",
        "config": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-postgres"]
        },
        "env_required": ["DATABASE_URL"]
    },
    "google-maps": {
        "description": "Provide directions, routing, and places search using Google Maps API.",
        "config": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-google-maps"]
        },
        "env_required": ["GOOGLE_MAPS_API_KEY"]
    }
}


class SearchMCPRegistryTool(Tool):
    """Tool for browsing the official open-source MCP skills directory."""

    @property
    def name(self) -> str:
        return "search_mcp_registry"

    @property
    def description(self) -> str:
        return (
            "Browse the official list of verified MCP (Model Context Protocol) skills that you can install to expand your capabilities. "
            "Use this if you are missing a capability (like web search, database access, map routing) and want to see if a verified plugin exists. "
            "Returns a JSON listing of skill IDs, their descriptions, and the required environment variables needed to use them."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }

    async def execute(self, **kwargs: Any) -> str:
        registry_dump = {}
        for skill_id, details in VERIFIED_SKILLS.items():
            registry_dump[skill_id] = {
                "description": details["description"],
                "env_vars_needed": details["env_required"]
            }
        
        return (
            "--- OFFICIAL VERIFIED NANOBOT MCP SKILLS REGISTRY ---\n\n"
            f"{json.dumps(registry_dump, indent=2)}\n\n"
            "If you found a skill that solves your problem, you MUST first ask the Tamer for permission to install it. "
            "If they say 'yes', use the `install_skill` tool with the appropriate skill_id."
        )
