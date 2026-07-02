"""Validation helpers for the JSON action protocol."""

from __future__ import annotations

import json
from typing import Any

TOOL_SCHEMAS: dict[str, dict[str, type | tuple[type, ...]]] = {
    "list_files": {"path": str, "max_files": int},
    "repo_map": {"path": str, "query": str, "max_files": int},
    "context_pack": {"query": str, "path": str, "max_files": int, "max_chars": int},
    "read_file": {"path": str, "start_line": int, "end_line": int},
    "write_file": {"path": str, "content": str, "overwrite": bool},
    "apply_patch": {"patch": str, "check_only": bool},
    "search_text": {"pattern": str, "path": str, "max_results": int},
    "git_diff": {"path": str, "max_chars": int},
    "discover_tests": {},
    "run_shell": {"command": str},
    "finish": {"message": str},
}

REQUIRED_ARGS: dict[str, set[str]] = {
    "context_pack": {"query"},
    "read_file": {"path"},
    "write_file": {"path", "content"},
    "apply_patch": {"patch"},
    "search_text": {"pattern"},
    "run_shell": {"command"},
}


def validate_action(action: dict[str, Any]) -> list[str]:
    """Return validation errors for a parsed model action."""

    errors: list[str] = []
    tool = action.get("tool")
    if not isinstance(tool, str) or not tool.strip():
        return ["field 'tool' must be a non-empty string"]
    tool = tool.strip()
    if tool not in TOOL_SCHEMAS:
        return [f"unknown tool: {tool}"]

    args = action.get("args", {})
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return ["field 'args' must be an object"]

    note = action.get("note", "")
    if note is not None and not isinstance(note, str):
        errors.append("field 'note' must be a string when present")

    for required in sorted(REQUIRED_ARGS.get(tool, set())):
        if required not in args:
            errors.append(f"tool '{tool}' missing required arg: {required}")

    allowed = TOOL_SCHEMAS[tool]
    for key, value in args.items():
        expected = allowed.get(key)
        if expected is None:
            errors.append(f"tool '{tool}' does not support arg: {key}")
            continue
        if value is not None and not isinstance(value, expected):
            errors.append(f"tool '{tool}' arg '{key}' must be {type_name(expected)}")
    return errors


def build_action_repair_prompt(*, error: str, raw_response: str) -> str:
    """Build a compact prompt asking the model to repair one action."""

    tools = ", ".join(sorted(TOOL_SCHEMAS))
    return "\n".join(
        [
            "Your previous response did not match the cagent JSON action protocol.",
            f"Error: {error}",
            "Return exactly one corrected JSON object and no extra text.",
            f"Valid tools: {tools}",
            "Required format:",
            json.dumps({"tool": "repo_map", "args": {"query": "relevant topic"}, "note": "brief reason"}),
            "Previous response:",
            raw_response[:2000],
        ]
    )


def type_name(expected: type | tuple[type, ...]) -> str:
    if isinstance(expected, tuple):
        return "|".join(item.__name__ for item in expected)
    return expected.__name__
