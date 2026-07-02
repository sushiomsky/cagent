"""Workspace-scoped tools used by the agent loop."""

from __future__ import annotations

import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cagent.approval_queue import create_approval_request
from cagent.command_policy import evaluate_command, normalize_command_profile
from cagent.repomap import build_context_pack, build_repo_map, format_context_pack, format_repo_map
from cagent.secret_scan import redact_text


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
    ".cagent-runs",
    "dist",
    "build",
}


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    output: str

    def as_message(self) -> str:
        status = "ok" if self.ok else "error"
        return f"TOOL_RESULT status={status}\n{self.output}"


class WorkspaceTools:
    def __init__(
        self,
        *,
        workspace: Path,
        allow_write: bool,
        allow_shell: bool,
        dry_run: bool,
        shell_timeout_seconds: int,
        command_profile: str = "inspect",
        auto_approve_shell: bool = False,
        redact_secrets: bool = True,
    ) -> None:
        self.workspace = workspace.resolve()
        self.allow_write = allow_write
        self.allow_shell = allow_shell
        self.dry_run = dry_run
        self.shell_timeout_seconds = shell_timeout_seconds
        self.command_profile = normalize_command_profile(command_profile)
        self.auto_approve_shell = auto_approve_shell
        self.redact_secrets = redact_secrets

    def execute(self, tool: str, args: dict[str, Any]) -> ToolResult:
        try:
            if tool == "list_files":
                return self.list_files(path=str(args.get("path", ".")), max_files=int(args.get("max_files", 200)))
            if tool == "repo_map":
                return self.repo_map(
                    path=str(args.get("path", ".")),
                    query=str(args.get("query", "")),
                    max_files=int(args.get("max_files", 80)),
                )
            if tool == "context_pack":
                return self.context_pack(
                    query=str(args.get("query", "")),
                    path=str(args.get("path", ".")),
                    max_files=int(args.get("max_files", 8)),
                    max_chars=int(args.get("max_chars", 30_000)),
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
            if tool == "apply_patch":
                return self.apply_patch(patch=str(args["patch"]), check_only=bool(args.get("check_only", False)))
            if tool == "search_text":
                return self.search_text(
                    pattern=str(args["pattern"]),
                    path=str(args.get("path", ".")),
                    max_results=int(args.get("max_results", 50)),
                )
            if tool == "git_diff":
                return self.git_diff(path=str(args.get("path", ".")), max_chars=int(args.get("max_chars", 40_000)))
            if tool == "discover_tests":
                return self.discover_tests()
            if tool == "run_shell":
                return self.run_shell(command=str(args["command"]))
        except KeyError as exc:
            return ToolResult(False, f"Missing required tool argument: {exc}")
        except Exception as exc:  # noqa: BLE001
            return ToolResult(False, self._redact(f"Tool failed: {type(exc).__name__}: {exc}"))
        return ToolResult(False, f"Unknown tool: {tool}")

    def resolve_path(self, path: str) -> Path:
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

    def repo_map(self, *, path: str = ".", query: str = "", max_files: int = 80) -> ToolResult:
        files = build_repo_map(self.workspace, path=path, query=query, max_files=max_files)
        return ToolResult(True, format_repo_map(files))

    def context_pack(self, *, query: str, path: str = ".", max_files: int = 8, max_chars: int = 30_000) -> ToolResult:
        pack = build_context_pack(self.workspace, query=query, path=path, max_files=max_files, max_chars=max_chars)
        return ToolResult(True, self._redact(format_context_pack(pack)))

    def read_file(self, *, path: str, start_line: int | None = None, end_line: int | None = None, max_chars: int = 30_000) -> ToolResult:
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
        return ToolResult(True, self._redact(output))

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

    def apply_patch(self, *, patch: str, check_only: bool = False) -> ToolResult:
        if not patch.strip():
            return ToolResult(False, "Patch is empty.")
        if not check_only and not self.allow_write:
            return ToolResult(False, "Patch application is disabled. Re-run with --write to allow changes.")
        check = self._run_git_apply(["git", "apply", "--check", "--whitespace=nowarn"], patch)
        if check.returncode != 0:
            return ToolResult(False, self._redact(_format_completed_process(check)))
        if check_only or self.dry_run:
            prefix = "Dry-run: " if self.dry_run and not check_only else ""
            return ToolResult(True, f"{prefix}patch check passed; no files were changed.")
        applied = self._run_git_apply(["git", "apply", "--whitespace=nowarn"], patch)
        return ToolResult(applied.returncode == 0, self._redact(_format_completed_process(applied)))

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
                text = file_path.read_text(encoding="utf-8", errors="replace")
                for line_no, line in enumerate(text.splitlines(), start=1):
                    if regex.search(line):
                        results.append(f"{relative}:{line_no}: {line}")
                        if len(results) >= max_results:
                            return ToolResult(True, self._redact("\n".join(results) + "\n... truncated ..."))
            except OSError as exc:
                results.append(f"{relative}: could not read: {exc}")
        return ToolResult(True, self._redact("\n".join(results) if results else "No matches."))

    def git_diff(self, *, path: str = ".", max_chars: int = 40_000) -> ToolResult:
        resolved = self.resolve_path(path)
        relative = "." if resolved == self.workspace else str(resolved.relative_to(self.workspace))
        status = _run_command(["git", "status", "--short", "--untracked-files=all", "--", relative], cwd=self.workspace, timeout_seconds=self.shell_timeout_seconds, input_text=None)
        diff = _run_command(["git", "diff", "--", relative], cwd=self.workspace, timeout_seconds=self.shell_timeout_seconds, input_text=None)
        if status.returncode != 0:
            return ToolResult(False, self._redact(_format_completed_process(status)))
        if diff.returncode != 0:
            return ToolResult(False, self._redact(_format_completed_process(diff)))
        output = f"--- git status --short ---\n{status.stdout}\n--- git diff ---\n{diff.stdout}"
        if len(output) > max_chars:
            output = output[:max_chars] + "\n... truncated ..."
        return ToolResult(True, self._redact(output))

    def discover_tests(self) -> ToolResult:
        candidates: list[str] = []
        if (self.workspace / "pyproject.toml").exists() or (self.workspace / "pytest.ini").exists():
            candidates.append("pytest -q")
        if (self.workspace / "package.json").exists():
            candidates.append("npm test")
        if (self.workspace / "pnpm-lock.yaml").exists():
            candidates.insert(0, "pnpm test")
        if (self.workspace / "yarn.lock").exists():
            candidates.insert(0, "yarn test")
        if (self.workspace / "go.mod").exists():
            candidates.append("go test ./...")
        if (self.workspace / "Cargo.toml").exists():
            candidates.append("cargo test")
        if (self.workspace / "composer.json").exists():
            candidates.append("composer test")
        if not candidates:
            return ToolResult(True, "No obvious test command found.")
        return ToolResult(True, "Suggested test commands:\n" + "\n".join(f"- {item}" for item in candidates))

    def run_shell(self, *, command: str) -> ToolResult:
        if not self.allow_shell:
            return ToolResult(False, "Shell access is disabled. Re-run with --shell to allow commands.")
        decision = evaluate_command(command, profile=self.command_profile)
        if decision.blocked:
            return ToolResult(False, f"Blocked by command profile '{decision.profile}': {decision.reason}")
        if decision.requires_approval and not self.auto_approve_shell:
            request = create_approval_request(
                self.workspace,
                action_type="shell",
                title=f"Approve command under {decision.profile} profile",
                reason=decision.reason,
                command=command,
                payload={"profile": decision.profile, "policy_level": decision.level, "tool": "run_shell"},
            )
            return ToolResult(False, f"Command requires approval before execution. Created approval request {request.id}. Reason: {decision.reason}.")
        if self.dry_run:
            approval_note = " would require approval" if decision.requires_approval else ""
            return ToolResult(True, f"Dry-run: would execute under profile '{decision.profile}'{approval_note}: {command}")
        argv = shlex.split(command)
        if not argv:
            return ToolResult(False, "Command is empty.")
        completed = subprocess.run(
            argv,
            cwd=self.workspace,
            text=True,
            capture_output=True,
            timeout=self.shell_timeout_seconds,
            env=_safe_env(),
            check=False,
        )
        output = f"policy={decision.level} profile={decision.profile} reason={decision.reason}\n"
        output += _format_completed_process(completed)
        if len(output) > 40_000:
            output = output[:40_000] + "\n... truncated ..."
        return ToolResult(completed.returncode == 0, self._redact(output))

    def _run_git_apply(self, command: list[str], patch: str) -> subprocess.CompletedProcess[str]:
        return _run_command(command, cwd=self.workspace, timeout_seconds=self.shell_timeout_seconds, input_text=patch)

    def _redact(self, output: str) -> str:
        if not self.redact_secrets:
            return output
        return redact_text(output)


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


def _run_command(command: list[str], *, cwd: Path, timeout_seconds: int, input_text: str | None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, input=input_text, text=True, capture_output=True, timeout=timeout_seconds, env=_safe_env(), check=False)


def _format_completed_process(completed: subprocess.CompletedProcess[str]) -> str:
    return f"exit_code={completed.returncode}\n--- stdout ---\n{completed.stdout}\n--- stderr ---\n{completed.stderr}"


def _safe_env() -> dict[str, str]:
    keep = {"HOME", "PATH", "LANG", "LC_ALL", "VIRTUAL_ENV", "PYTHONPATH", "PIP_DISABLE_PIP_VERSION_CHECK"}
    return {key: value for key, value in os.environ.items() if key in keep}


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)
