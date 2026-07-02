"""Workspace-scoped tools used by the agent loop."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SKIPPED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "dist",
    "build",
}

DANGEROUS_COMMAND_PATTERNS = [
    r"\brm\s+-rf\s+/(\s|$)",
    r"\brm\s+-rf\s+~(\s|$)",
    r"\bdd\s+if=",
    r"\bmkfs\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r":\s*\(\)\s*\{",
    r"\bchmod\s+-R\s+777\s+/(\s|$)",
    r"\bchown\s+-R\b.*\s+/(\s|$)",
]


@dataclass(frozen=True)
class ToolResult:
    """Text result returned to the model after a tool call."""

    ok: bool
    output: str

    def as_message(self) -> str:
        status = "ok" if self.ok else "error"
        return f"TOOL_RESULT status={status}\n{self.output}"


class WorkspaceTools:
    """Safe-ish tools restricted to one workspace root."""

    def __init__(
        self,
        *,
        workspace: Path,
        allow_write: bool,
        allow_shell: bool,
        dry_run: bool,
        shell_timeout_seconds: int,
    ) -> None:
        self.workspace = workspace.resolve()
        self.allow_write = allow_write
        self.allow_shell = allow_shell
        self.dry_run = dry_run
        self.shell_timeout_seconds = shell_timeout_seconds

    def execute(self, tool: str, args: dict[str, Any]) -> ToolResult:
        """Dispatch a parsed model action to a concrete tool."""

        try:
            if tool == "list_files":
                return self.list_files(
                    path=str(args.get("path", ".")),
                    max_files=int(args.get("max_files", 200)),
                )
            if tool == "read_file":
                return self.read_file(
                    path=str(args["path"]),
                    start_line=_optional_int(args.get("start_line")),
                    end_line=_optional_int(args.get("end_line")),
                )
            if tool == "write_file":
                return self.write_file(
                    path=str(args["path"]),
                    content=str(args.get("content", "")),
                    overwrite=bool(args.get("overwrite", True)),
                )
            if tool == "search_text":
                return self.search_text(
                    pattern=str(args["pattern"]),
                    path=str(args.get("path", ".")),
                    max_results=int(args.get("max_results", 50)),
                )
            if tool == "run_shell":
                return self.run_shell(command=str(args["command"]))
        except KeyError as exc:
            return ToolResult(False, f"Missing required tool argument: {exc}")
        except Exception as exc:  # noqa: BLE001 - tool errors must be returned to the model.
            return ToolResult(False, f"Tool failed: {type(exc).__name__}: {exc}")

        return ToolResult(False, f"Unknown tool: {tool}")

    def resolve_path(self, path: str) -> Path:
        """Resolve a user/model supplied path and reject workspace escapes."""

        candidate = (self.workspace / path).resolve()
        if candidate != self.workspace and self.workspace not in candidate.parents:
            raise ValueError(f"Path escapes workspace: {path}")
        return candidate

    def list_files(self, *, path: str = ".", max_files: int = 200) -> ToolResult:
        root = self.resolve_path(path)
        if not root.exists():
            return ToolResult(False, f"Path does not exist: {path}")

        files: list[str] = []
        if root.is_file():
            return ToolResult(True, str(root.relative_to(self.workspace)))

        for current_root, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(name for name in dirnames if name not in SKIPPED_DIRS)
            for filename in sorted(filenames):
                full_path = Path(current_root) / filename
                files.append(str(full_path.relative_to(self.workspace)))
                if len(files) >= max_files:
                    return ToolResult(True, "\n".join(files) + "\n... truncated ...")

        return ToolResult(True, "\n".join(files) if files else "No files found.")

    def read_file(
        self,
        *,
        path: str,
        start_line: int | None = None,
        end_line: int | None = None,
        max_chars: int = 30_000,
    ) -> ToolResult:
        full_path = self.resolve_path(path)
        if not full_path.exists():
            return ToolResult(False, f"File does not exist: {path}")
        if not full_path.is_file():
            return ToolResult(False, f"Path is not a file: {path}")

        text = full_path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        first = max((start_line or 1), 1)
        last = min((end_line or len(lines)), len(lines))
        selected = lines[first - 1 : last]
        numbered = [f"{line_no}: {line}" for line_no, line in enumerate(selected, start=first)]
        output = "\n".join(numbered)
        if len(output) > max_chars:
            output = output[:max_chars] + "\n... truncated ..."
        return ToolResult(True, output)

    def write_file(self, *, path: str, content: str, overwrite: bool = True) -> ToolResult:
        if not self.allow_write:
            return ToolResult(False, "Write access is disabled. Re-run with --write to allow file changes.")

        full_path = self.resolve_path(path)
        if full_path.exists() and not overwrite:
            return ToolResult(False, f"File exists and overwrite=false: {path}")

        if self.dry_run:
            return ToolResult(True, f"Dry-run: would write {len(content)} bytes to {path}")

        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return ToolResult(True, f"Wrote {len(content)} bytes to {path}")

    def search_text(self, *, pattern: str, path: str = ".", max_results: int = 50) -> ToolResult:
        root = self.resolve_path(path)
        if not root.exists():
            return ToolResult(False, f"Path does not exist: {path}")

        regex = re.compile(pattern, re.IGNORECASE)
        results: list[str] = []
        files = [root] if root.is_file() else _iter_text_files(root)

        for file_path in files:
            relative = file_path.relative_to(self.workspace)
            try:
                for line_no, line in enumerate(file_path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
                    if regex.search(line):
                        results.append(f"{relative}:{line_no}: {line}")
                        if len(results) >= max_results:
                            return ToolResult(True, "\n".join(results) + "\n... truncated ...")
            except OSError as exc:
                results.append(f"{relative}: could not read: {exc}")

        return ToolResult(True, "\n".join(results) if results else "No matches.")

    def run_shell(self, *, command: str) -> ToolResult:
        if not self.allow_shell:
            return ToolResult(False, "Shell access is disabled. Re-run with --shell to allow commands.")
        if _looks_dangerous(command):
            return ToolResult(False, f"Blocked dangerous command: {command}")
        if self.dry_run:
            return ToolResult(True, f"Dry-run: would execute: {command}")

        completed = subprocess.run(
            command,
            cwd=self.workspace,
            shell=True,
            text=True,
            capture_output=True,
            timeout=self.shell_timeout_seconds,
            env=_safe_env(),
            check=False,
        )
        output = (
            f"exit_code={completed.returncode}\n"
            f"--- stdout ---\n{completed.stdout}\n"
            f"--- stderr ---\n{completed.stderr}"
        )
        if len(output) > 40_000:
            output = output[:40_000] + "\n... truncated ..."
        return ToolResult(completed.returncode == 0, output)


def _iter_text_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in SKIPPED_DIRS)
        for filename in sorted(filenames):
            full_path = Path(current_root) / filename
            if _is_probably_text_file(full_path):
                files.append(full_path)
    return files


def _is_probably_text_file(path: Path) -> bool:
    try:
        chunk = path.read_bytes()[:2048]
    except OSError:
        return False
    return b"\x00" not in chunk


def _looks_dangerous(command: str) -> bool:
    return any(re.search(pattern, command) for pattern in DANGEROUS_COMMAND_PATTERNS)


def _safe_env() -> dict[str, str]:
    keep = {
        "HOME",
        "PATH",
        "LANG",
        "LC_ALL",
        "VIRTUAL_ENV",
        "PYTHONPATH",
        "PIP_DISABLE_PIP_VERSION_CHECK",
    }
    return {key: value for key, value in os.environ.items() if key in keep}


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)
