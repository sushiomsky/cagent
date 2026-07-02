"""Line-delimited JSON-RPC server for cagent adapters.

This is a small stdio adapter inspired by MCP's JSON-RPC transport model. It is
kept dependency-free and intentionally exposes conservative project-state tools.
A full MCP SDK/server implementation can be layered on top later without
changing the underlying cagent project engine.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from cagent.mcp_manifest import build_manifest
from cagent.project_engine import next_action, verify_project, write_final_report
from cagent.secret_scan import format_findings, scan_workspace
from cagent.trust import format_trust_status, trust_workspace

JSONRPC_VERSION = "2.0"
SERVER_NAME = "cagent-stdio"
SERVER_VERSION = "0.1"

RESOURCE_FILES: dict[str, str] = {
    "cagent://project/spec": "PROJECT_SPEC.md",
    "cagent://project/tasks": "TASKS.md",
    "cagent://project/workflow": "WORKFLOW.md",
    "cagent://project/agents": "AGENTS.md",
    "cagent://project/final-report": "FINAL_REPORT.md",
    "cagent://project/snapshot": ".cagent/snapshot.json",
}


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]


TOOLS: tuple[ToolDefinition, ...] = (
    ToolDefinition(
        name="cagent.resume",
        description="Read .cagent state and return the next project action.",
        input_schema={
            "type": "object",
            "properties": {"workspace": {"type": "string", "default": "."}},
        },
    ),
    ToolDefinition(
        name="cagent.verify",
        description="Verify project scaffolding and task state.",
        input_schema={
            "type": "object",
            "properties": {"workspace": {"type": "string", "default": "."}},
        },
    ),
    ToolDefinition(
        name="cagent.secret_scan",
        description="Scan workspace files for likely secrets.",
        input_schema={
            "type": "object",
            "properties": {
                "workspace": {"type": "string", "default": "."},
                "max_files": {"type": "integer", "default": 1000},
            },
        },
    ),
    ToolDefinition(
        name="cagent.trust_status",
        description="Return local workspace trust status.",
        input_schema={
            "type": "object",
            "properties": {"workspace": {"type": "string", "default": "."}},
        },
    ),
    ToolDefinition(
        name="cagent.trust",
        description="Mark a workspace as reviewed/trusted.",
        input_schema={
            "type": "object",
            "properties": {
                "workspace": {"type": "string", "default": "."},
                "reason": {"type": "string", "default": "Trusted through stdio adapter."},
            },
        },
    ),
    ToolDefinition(
        name="cagent.final_report",
        description="Generate FINAL_REPORT.md from project state.",
        input_schema={
            "type": "object",
            "properties": {
                "workspace": {"type": "string", "default": "."},
                "notes": {"type": "string", "default": "Generated through stdio adapter."},
            },
        },
    ),
    ToolDefinition(
        name="cagent.manifest",
        description="Return the cagent capability manifest.",
        input_schema={"type": "object", "properties": {}},
    ),
)


class RpcError(RuntimeError):
    def __init__(self, code: int, message: str, data: Any | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


def serve_stdio(stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> int:
    """Serve line-delimited JSON-RPC requests until EOF or shutdown."""

    for raw_line in stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            response = handle_json_line(line)
        except Exception as exc:  # noqa: BLE001 - top-level protocol boundary.
            response = error_response(None, -32603, f"internal error: {type(exc).__name__}: {exc}")
        if response is not None:
            stdout.write(json.dumps(response, ensure_ascii=False, sort_keys=True) + "\n")
            stdout.flush()
            if response.get("result") == {"shutdown": True}:
                return 0
    return 0


def handle_json_line(line: str) -> dict[str, Any] | None:
    try:
        request = json.loads(line)
    except json.JSONDecodeError as exc:
        return error_response(None, -32700, f"parse error: {exc}")
    return handle_request(request)


def handle_request(request: Any) -> dict[str, Any] | None:
    if not isinstance(request, dict):
        return error_response(None, -32600, "request must be an object")

    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params") or {}
    if not isinstance(method, str):
        return error_response(request_id, -32600, "method must be a string")
    if not isinstance(params, dict):
        return error_response(request_id, -32602, "params must be an object")

    try:
        if method == "initialize":
            result = initialize_result()
        elif method == "tools/list":
            result = {"tools": [tool_to_dict(tool) for tool in TOOLS]}
        elif method == "tools/call":
            result = call_tool(params)
        elif method == "resources/list":
            result = {"resources": list_resources(params)}
        elif method == "resources/read":
            result = read_resource(params)
        elif method == "shutdown":
            result = {"shutdown": True}
        else:
            raise RpcError(-32601, f"method not found: {method}")
    except RpcError as exc:
        return error_response(request_id, exc.code, exc.message, exc.data)

    if request_id is None:
        return None
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}


def initialize_result() -> dict[str, Any]:
    return {
        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        "capabilities": {"tools": {"listChanged": False}, "resources": {"listChanged": False}},
        "instructions": "Use tools/list, tools/call, resources/list and resources/read for conservative cagent project-state access.",
    }


def call_tool(params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name")
    arguments = params.get("arguments") or {}
    if not isinstance(name, str):
        raise RpcError(-32602, "tools/call requires string field: name")
    if not isinstance(arguments, dict):
        raise RpcError(-32602, "tools/call arguments must be an object")

    if name == "cagent.resume":
        text = next_action(_workspace(arguments))
    elif name == "cagent.verify":
        text = _format_verification(_workspace(arguments))
    elif name == "cagent.secret_scan":
        text = format_findings(scan_workspace(_workspace(arguments), max_files=int(arguments.get("max_files", 1000))))
    elif name == "cagent.trust_status":
        text = format_trust_status(_workspace(arguments))
    elif name == "cagent.trust":
        workspace = _workspace(arguments)
        trust_workspace(workspace, reason=str(arguments.get("reason") or "Trusted through stdio adapter."))
        text = format_trust_status(workspace)
    elif name == "cagent.final_report":
        path = write_final_report(_workspace(arguments), notes=str(arguments.get("notes") or "Generated through stdio adapter."))
        text = f"final report: {path}"
    elif name == "cagent.manifest":
        return {"content": [{"type": "json", "json": build_manifest()}], "isError": False}
    else:
        raise RpcError(-32602, f"unknown tool: {name}")

    return {"content": [{"type": "text", "text": text}], "isError": False}


def list_resources(params: dict[str, Any]) -> list[dict[str, Any]]:
    workspace = _workspace(params)
    resources: list[dict[str, Any]] = []
    for uri, relative in RESOURCE_FILES.items():
        path = workspace / relative
        resources.append(
            {
                "uri": uri,
                "name": Path(relative).name,
                "mimeType": "application/json" if path.suffix == ".json" else "text/markdown",
                "exists": path.exists(),
            }
        )
    return resources


def read_resource(params: dict[str, Any]) -> dict[str, Any]:
    uri = params.get("uri")
    if not isinstance(uri, str) or uri not in RESOURCE_FILES:
        raise RpcError(-32602, "resources/read requires a known uri")
    workspace = _workspace(params)
    path = (workspace / RESOURCE_FILES[uri]).resolve()
    if workspace not in path.parents and path != workspace:
        raise RpcError(-32602, "resource path escapes workspace")
    if not path.exists():
        raise RpcError(-32004, f"resource not found: {uri}")
    text = path.read_text(encoding="utf-8", errors="replace")
    return {"contents": [{"uri": uri, "mimeType": _mime_type(path), "text": text}]}


def tool_to_dict(tool: ToolDefinition) -> dict[str, Any]:
    return {
        "name": tool.name,
        "description": tool.description,
        "inputSchema": tool.input_schema,
    }


def error_response(request_id: Any, code: int, message: str, data: Any | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "error": error}


def _workspace(arguments: dict[str, Any]) -> Path:
    return Path(str(arguments.get("workspace") or ".")).resolve()


def _format_verification(workspace: Path) -> str:
    result = verify_project(workspace)
    lines = [f"status: {'PASS' if result.ok else 'NEEDS_WORK'}"]
    lines.extend(f"ok: {item}" for item in result.checks)
    lines.extend(f"warn: {item}" for item in result.warnings)
    lines.extend(f"missing: {item}" for item in result.missing)
    return "\n".join(lines)


def _mime_type(path: Path) -> str:
    return "application/json" if path.suffix == ".json" else "text/markdown"
