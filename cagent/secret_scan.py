"""Secret scanning and redaction helpers for cagent.

This is a lightweight local guardrail, not a replacement for a dedicated secret
scanner. It focuses on common high-risk patterns and conservative redaction
before tool output is sent back to the model.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Pattern


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


@dataclass(frozen=True)
class SecretPattern:
    kind: str
    regex: Pattern[str]


@dataclass(frozen=True)
class SecretFinding:
    path: str
    line: int
    kind: str
    preview: str


SECRET_PATTERNS = [
    SecretPattern("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    SecretPattern("openai_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    SecretPattern("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    SecretPattern("github_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b")),
    SecretPattern("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    SecretPattern("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    SecretPattern(
        "env_secret_assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret|token|password|passwd|private[_-]?key|client[_-]?secret)\s*=\s*['\"]?[^'\"\s]{8,}"
        ),
    ),
]


def scan_text(text: str, *, path: str = "<text>") -> list[SecretFinding]:
    """Return likely secret findings in text."""

    findings: list[SecretFinding] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for pattern in SECRET_PATTERNS:
            if pattern.regex.search(line):
                findings.append(
                    SecretFinding(
                        path=path,
                        line=line_no,
                        kind=pattern.kind,
                        preview=redact_text(line.strip())[:200],
                    )
                )
    return findings


def redact_text(text: str) -> str:
    """Redact likely secrets in text while preserving surrounding context."""

    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.regex.sub(lambda match, kind=pattern.kind: _redaction(kind, match.group(0)), redacted)
    return redacted


def scan_file(path: Path, *, workspace: Path | None = None) -> list[SecretFinding]:
    if not _is_scannable_file(path):
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    display_path = str(path if workspace is None else path.relative_to(workspace))
    return scan_text(text, path=display_path)


def scan_workspace(workspace: Path, *, max_files: int = 1000) -> list[SecretFinding]:
    """Scan a workspace for likely secrets."""

    root = workspace.resolve()
    findings: list[SecretFinding] = []
    scanned = 0
    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in SKIP_DIRS)
        for filename in sorted(filenames):
            path = Path(current_root) / filename
            if not _is_scannable_file(path):
                continue
            findings.extend(scan_file(path, workspace=root))
            scanned += 1
            if scanned >= max_files:
                return findings
    return findings


def format_findings(findings: list[SecretFinding]) -> str:
    if not findings:
        return "No likely secrets found."
    lines = ["Likely secrets found:"]
    for finding in findings:
        lines.append(f"- {finding.path}:{finding.line} [{finding.kind}] {finding.preview}")
    return "\n".join(lines)


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
