"""Shell command policy for cagent.

This is not a sandbox. It is a practical guardrail layer that classifies shell
commands before execution and lets users choose a command profile for a run.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from typing import Literal

CommandProfile = Literal["inspect", "test", "edit", "network", "deploy"]
RiskLevel = Literal["allow", "approval", "block"]

VALID_COMMAND_PROFILES: tuple[CommandProfile, ...] = (
    "inspect",
    "test",
    "edit",
    "network",
    "deploy",
)

ABSOLUTELY_BLOCKED_PATTERNS = [
    r"\brm\s+-rf\s+/(\s|$)",
    r"\brm\s+-rf\s+~(\s|$)",
    r"\bdd\s+if=",
    r"\bmkfs\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r":\s*\(\)\s*\{",
    r"\bchmod\s+-R\s+777\s+/(\s|$)",
    r"\bchown\s+-R\b.*\s+/(\s|$)",
    r"\bsudo\b",
    r"\bsu\b",
]

NETWORK_TOKENS = {
    "curl",
    "wget",
    "ssh",
    "scp",
    "rsync",
    "nc",
    "ncat",
    "telnet",
    "tailscale",
}

INSTALL_TOKENS = {
    "apt",
    "apt-get",
    "apk",
    "dnf",
    "yum",
    "pacman",
    "brew",
    "pip",
    "pip3",
    "npm",
    "pnpm",
    "yarn",
    "cargo",
    "go",
}

WRITE_TOKENS = {
    "touch",
    "mkdir",
    "cp",
    "mv",
    "rm",
    "sed",
    "tee",
    "truncate",
    "python",
    "python3",
    "node",
}

TEST_TOKENS = {
    "pytest",
    "python",
    "python3",
    "npm",
    "pnpm",
    "yarn",
    "go",
    "cargo",
    "composer",
    "make",
}

INSPECT_TOKENS = {
    "cat",
    "cd",
    "du",
    "echo",
    "env",
    "false",
    "file",
    "find",
    "git",
    "grep",
    "head",
    "jq",
    "less",
    "ls",
    "pwd",
    "rg",
    "sort",
    "tail",
    "test",
    "true",
    "wc",
    "which",
}

GIT_WRITE_SUBCOMMANDS = {
    "add",
    "am",
    "apply",
    "bisect",
    "branch",
    "checkout",
    "cherry-pick",
    "clean",
    "commit",
    "merge",
    "mv",
    "pull",
    "push",
    "rebase",
    "reset",
    "restore",
    "revert",
    "rm",
    "stash",
    "switch",
    "tag",
}

GIT_NETWORK_SUBCOMMANDS = {"clone", "fetch", "pull", "push", "remote", "submodule"}


@dataclass(frozen=True)
class CommandDecision:
    """Policy decision for a shell command."""

    level: RiskLevel
    reason: str
    profile: CommandProfile

    @property
    def allowed_without_approval(self) -> bool:
        return self.level == "allow"

    @property
    def requires_approval(self) -> bool:
        return self.level == "approval"

    @property
    def blocked(self) -> bool:
        return self.level == "block"


def normalize_command_profile(profile: str | None) -> CommandProfile:
    """Normalize and validate a command profile."""

    value = (profile or "inspect").strip().lower()
    if value not in VALID_COMMAND_PROFILES:
        valid = ", ".join(VALID_COMMAND_PROFILES)
        raise ValueError(f"Invalid command profile '{profile}'. Expected one of: {valid}")
    return value  # type: ignore[return-value]


def evaluate_command(command: str, *, profile: str | None = None) -> CommandDecision:
    """Classify a shell command for the selected profile."""

    selected = normalize_command_profile(profile)
    normalized = command.strip()
    if not normalized:
        return CommandDecision("block", "empty command", selected)

    for pattern in ABSOLUTELY_BLOCKED_PATTERNS:
        if re.search(pattern, normalized):
            return CommandDecision("block", f"blocked by absolute safety pattern: {pattern}", selected)

    first_token = _first_token(normalized)
    if not first_token:
        return CommandDecision("block", "could not parse command", selected)

    if _uses_shell_control_flow(normalized):
        return _decision_for_complex_shell(selected)

    if first_token == "git":
        return _decision_for_git(normalized, selected)

    if first_token in NETWORK_TOKENS:
        return _decision_for_network(first_token, selected)

    if first_token in INSTALL_TOKENS and _looks_like_install_or_network(normalized):
        return _decision_for_install(first_token, selected)

    if first_token in TEST_TOKENS and _looks_like_test_command(normalized):
        return _decision_for_test(first_token, selected)

    if _looks_like_write_command(first_token, normalized):
        return _decision_for_write(first_token, selected)

    if first_token in INSPECT_TOKENS:
        return CommandDecision("allow", f"read-only inspect command: {first_token}", selected)

    if selected == "deploy":
        return CommandDecision("approval", f"unknown command in deploy profile: {first_token}", selected)

    return CommandDecision("block", f"command is not allowed in {selected} profile: {first_token}", selected)


def _first_token(command: str) -> str | None:
    try:
        parts = shlex.split(command, posix=True)
    except ValueError:
        return None
    if not parts:
        return None
    return parts[0].split("/")[-1]


def _tokens(command: str) -> list[str]:
    try:
        return shlex.split(command, posix=True)
    except ValueError:
        return []


def _uses_shell_control_flow(command: str) -> bool:
    return any(marker in command for marker in ["&&", "||", ";", "|", ">", "<", "`", "$("])


def _decision_for_complex_shell(profile: CommandProfile) -> CommandDecision:
    if profile == "deploy":
        return CommandDecision("approval", "complex shell command requires approval", profile)
    return CommandDecision("block", f"complex shell command is not allowed in {profile} profile", profile)


def _decision_for_git(command: str, profile: CommandProfile) -> CommandDecision:
    parts = _tokens(command)
    subcommand = parts[1] if len(parts) > 1 else ""
    if subcommand in GIT_NETWORK_SUBCOMMANDS:
        return _decision_for_network(f"git {subcommand}", profile)
    if subcommand in GIT_WRITE_SUBCOMMANDS:
        return _decision_for_write(f"git {subcommand}", profile)
    return CommandDecision("allow", f"read-only git command: git {subcommand or '<none>'}", profile)


def _decision_for_network(command_name: str, profile: CommandProfile) -> CommandDecision:
    if profile in {"network", "deploy"}:
        return CommandDecision("approval", f"network command requires approval: {command_name}", profile)
    return CommandDecision("block", f"network command requires network/deploy profile: {command_name}", profile)


def _decision_for_install(command_name: str, profile: CommandProfile) -> CommandDecision:
    if profile in {"network", "deploy"}:
        return CommandDecision("approval", f"install/dependency command requires approval: {command_name}", profile)
    return CommandDecision("block", f"install/dependency command requires network/deploy profile: {command_name}", profile)


def _decision_for_test(command_name: str, profile: CommandProfile) -> CommandDecision:
    if profile in {"test", "edit", "network", "deploy"}:
        return CommandDecision("allow", f"test command allowed: {command_name}", profile)
    return CommandDecision("block", f"test command requires test/edit/network/deploy profile: {command_name}", profile)


def _decision_for_write(command_name: str, profile: CommandProfile) -> CommandDecision:
    if profile in {"edit", "network", "deploy"}:
        return CommandDecision("approval", f"write-capable command requires approval: {command_name}", profile)
    return CommandDecision("block", f"write-capable command requires edit/network/deploy profile: {command_name}", profile)


def _looks_like_install_or_network(command: str) -> bool:
    lowered = command.lower()
    keywords = [
        " install",
        " add ",
        " update",
        " upgrade",
        " download",
        " publish",
        " push",
        " get ",
        " mod download",
    ]
    return any(keyword in f" {lowered} " for keyword in keywords)


def _looks_like_test_command(command: str) -> bool:
    lowered = command.lower()
    return any(
        marker in lowered
        for marker in [
            "pytest",
            " test",
            "tests",
            "go test",
            "cargo test",
            "npm test",
            "pnpm test",
            "yarn test",
            "composer test",
            "compileall",
        ]
    )


def _looks_like_write_command(first_token: str, command: str) -> bool:
    if first_token in WRITE_TOKENS:
        lowered = command.lower()
        if first_token in {"python", "python3", "node"}:
            return any(marker in lowered for marker in [" -c ", " -m ", "write(", "unlink", "rename", "remove"])
        return True
    return False
