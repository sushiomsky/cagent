"""Secret scanning and redaction helpers for cagent.

This is a lightweight local guardrail, not a replacement for a dedicated secret
scanner. It focuses on common high-risk patterns and conservative redaction
before tool output is sent back to the model.
"""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, Pattern

Severity = Literal["low", "medium", "high", "critical"]

SKIP_DIRS = {
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

SKIP_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".sqlite",
    ".db",
    ".pyc",
}

DEFAULT_ALLOWLIST_FILES = (".cagent-secret-allowlist", ".cagent/secret-allowlist")


@dataclass(frozen=True)
class SecretPattern:
    kind: str
    regex: Pattern[str]
    severity: Severity = "high"
    min_entropy: float = 0.0


@dataclass(frozen=True)
class SecretFinding:
    path: str
    line: int
    kind: str
    preview: str
    severity: Severity = "high"
    entropy: float = 0.0


SECRET_PATTERNS = [
    SecretPattern("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "critical"),
    SecretPattern("openai_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), "critical", 3.0),
    SecretPattern("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"), "critical", 3.0),
    SecretPattern("github_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b"), "critical", 3.0),
    SecretPattern("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"), "critical", 2.8),
    SecretPattern("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"), "high", 3.0),
    SecretPattern(
        "env_secret_assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret|token|password|passwd|private[_-]?key|client[_-]?secret)\s*=\s*['\"]?([^'\"\s]{8,})"
        ),
        "medium",
        2.6,
    ),
]


@dataclass(frozen=True)
class SecretAllowlist:
    patterns: tuple[Pattern[str], ...] = ()

    def allows(self, *, path: str, line: str, kind: str) -> bool:
        target = f"{path}:{kind}:{line}"
        return any(pattern.search(target) or pattern.search(line) for pattern in self.patterns)


def load_allowlist(workspace: Path) -> SecretAllowlist:
    """Load workspace allowlist regexes.

    Empty lines and comments are ignored. Invalid regexes are ignored so a bad
    allowlist never disables scanning entirely.
    """

    patterns: list[Pattern[str]] = []
    for relative in DEFAULT_ALLOWLIST_FILES:
        path = workspace / relative
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                patterns.append(re.compile(line))
            except re.error:
                continue
    return SecretAllowlist(tuple(patterns))


def scan_text(text: str, *, path: str = "<text>", allowlist: SecretAllowlist | None = None) -> list[SecretFinding]:
    """Return likely secret findings in text."""

    active_allowlist = allowlist or SecretAllowlist()
    findings: list[SecretFinding] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for pattern in SECRET_PATTERNS:
            match = pattern.regex.search(line)
            if not match:
                continue
            if active_allowlist.allows(path=path, line=line, kind=pattern.kind):
                continue
            candidate = _candidate_from_match(match)
            entropy = shannon_entropy(candidate)
            if pattern.min_entropy and entropy < pattern.min_entropy:
                continue
            findings.append(
                SecretFinding(
                    path=path,
                    line=line_no,
                    kind=pattern.kind,
                    preview=redact_text(line.strip())[:200],
                    severity=pattern.severity,
                    entropy=round(entropy, 2),
                )
            )
    return findings


def redact_text(text: str) -> str:
    """Redact likely secrets in text while preserving surrounding context."""

    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.regex.sub(lambda match, kind=pattern.kind: _redaction(kind, match.group(0)), redacted)
    return redacted


def scan_file(path: Path, *, workspace: Path | None = None, allowlist: SecretAllowlist | None = None) -> list[SecretFinding]:
    if not _is_scannable_file(path):
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    display_path = str(path if workspace is None else path.relative_to(workspace))
    return scan_text(text, path=display_path, allowlist=allowlist)


def scan_workspace(workspace: Path, *, max_files: int = 1000) -> list[SecretFinding]:
    """Scan a workspace for likely secrets."""

    root = workspace.resolve()
    allowlist = load_allowlist(root)
    findings: list[SecretFinding] = []
    scanned = 0
    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in SKIP_DIRS)
        for filename in sorted(filenames):
            path = Path(current_root) / filename
            if not _is_scannable_file(path):
                continue
            findings.extend(scan_file(path, workspace=root, allowlist=allowlist))
            scanned += 1
            if scanned >= max_files:
                return sorted_findings(findings)
    return sorted_findings(findings)


def sorted_findings(findings: list[SecretFinding]) -> list[SecretFinding]:
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(findings, key=lambda item: (order.get(item.severity, 9), item.path, item.line, item.kind))


def format_findings(findings: list[SecretFinding]) -> str:
    if not findings:
        return "No likely secrets found."
    lines = ["Likely secrets found:"]
    for finding in sorted_findings(findings):
        lines.append(
            f"- {finding.path}:{finding.line} [{finding.severity}/{finding.kind}] "
            f"entropy={finding.entropy:.2f} {finding.preview}"
        )
    return "\n".join(lines)


def findings_json(findings: list[SecretFinding]) -> str:
    return json.dumps([asdict(item) for item in sorted_findings(findings)], indent=2, sort_keys=True) + "\n"


def shannon_entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = {char: value.count(char) for char in set(value)}
    length = len(value)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def _candidate_from_match(match: re.Match[str]) -> str:
    if match.lastindex:
        return match.group(match.lastindex)
    value = match.group(0)
    if "=" in value:
        return value.split("=", 1)[1].strip().strip("'\"")
    return value


def _redaction(kind: str, value: str) -> str:
    if "=" in value and kind == "env_secret_assignment":
        key = value.split("=", 1)[0].rstrip()
        return f"{key}=<REDACTED:{kind}>"
    if len(value) <= 12:
        return f"<REDACTED:{kind}>"
    return f"{value[:4]}...<REDACTED:{kind}>...{value[-4:]}"


def _is_scannable_file(path: Path) -> bool:
    if path.suffix.lower() in SKIP_SUFFIXES:
        return False
    try:
        chunk = path.read_bytes()[:4096]
    except OSError:
        return False
    return b"\x00" not in chunk
