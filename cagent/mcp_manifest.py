"""MCP-style manifest export for cagent capabilities.

This is not a full MCP server yet. It gives downstream adapters a stable JSON
manifest of cagent commands and project-engine capabilities.
"""

from __future__ import annotations

import json
from typing import Any


def build_manifest() -> dict[str, Any]:
    """Return a stable manifest of exposed cagent capabilities."""

    return {
        "name": "cagent",
        "version": 1,
        "description": "Self-hosted coding and project agent with local project state.",
        "capabilities": [
            {
                "name": "run",
                "kind": "agent_loop",
                "description": "Run the JSON tool coding agent in a workspace.",
            },
            {
                "name": "init-project",
                "kind": "project_wizard",
                "description": "Create project spec, workflow, agents, tasks, tools and hooks.",
            },
            {
                "name": "loop",
                "kind": "project_loop",
                "description": "Run one iteration against the next project task.",
            },
            {
                "name": "resume",
                "kind": "state",
                "description": "Read .cagent state and show the next project action.",
            },
            {
                "name": "snapshot",
                "kind": "state",
                "description": "Read the compact .cagent project snapshot.",
            },
            {
                "name": "research",
                "kind": "research_notes",
                "description": "Create structured source notes in docs/research/.",
            },
            {
                "name": "tool",
                "kind": "tool_registry",
                "description": "Register planned or available project tools.",
            },
            {
                "name": "approval",
                "kind": "approval_queue",
                "description": "Create, list, approve and reject local approval requests.",
            },
            {
                "name": "verify",
                "kind": "verification",
                "description": "Check project state against required files and task state.",
            },
            {
                "name": "final-report",
                "kind": "report",
                "description": "Generate FINAL_REPORT.md from project state.",
            },
            {
                "name": "logs",
                "kind": "observability",
                "description": "List, inspect and render local .cagent-runs logs.",
            },
            {
                "name": "secret-scan",
                "kind": "security",
                "description": "Scan workspace files for likely secrets before a run or commit.",
            },
            {
                "name": "trust",
                "kind": "workspace_trust",
                "description": "Create or inspect local workspace trust metadata.",
            },
            {
                "name": "serve-stdio",
                "kind": "stdio_adapter",
                "description": "Run a line-delimited JSON-RPC stdio adapter exposing conservative cagent tools.",
            },
            {
                "name": "serve-web",
                "kind": "web_ui",
                "description": "Run a local dependency-free dashboard for project state, security, tasks and logs.",
            },
        ],
    }


def manifest_json() -> str:
    return json.dumps(build_manifest(), indent=2, sort_keys=True) + "\n"
