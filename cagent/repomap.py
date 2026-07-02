"""Repository map and context packing helpers.

This module intentionally avoids heavyweight parser dependencies. It gives the
agent a useful first-pass overview by combining filename ranking, simple import
extraction and regex-based symbol discovery.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


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

LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".php": "php",
    ".sh": "shell",
    ".bash": "shell",
    ".md": "markdown",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
}

SYMBOL_PATTERNS = [
    re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("),
    re.compile(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
    re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\("),
    re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:async\s*)?\(?"),
    re.compile(r"^\s*func\s+(?:\([^)]+\)\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*\("),
    re.compile(r"^\s*(?:pub\s+)?(?:async\s+)?fn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("),
    re.compile(r"^\s*(?:final\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
]

IMPORT_PATTERNS = [
    re.compile(r"^\s*(?:from\s+\S+\s+)?import\s+(.+)$"),
    re.compile(r"^\s*(?:import|export)\s+.+?\s+from\s+['\"]([^'\"]+)['\"]"),
    re.compile(r"^\s*const\s+.+?=\s+require\(['\"]([^'\"]+)['\"]\)"),
    re.compile(r"^\s*use\s+([^;]+);"),
    re.compile(r"^\s*require_once\s+[""']([^""']+)[""']"),
]


@dataclass(frozen=True)
class RepoFile:
    """One scanned repository file."""

    path: str
    language: str
    size_bytes: int
    line_count: int
    symbols: list[str]
    imports: list[str]
    score: int = 0


@dataclass(frozen=True)
class ContextPack:
    """Selected files and snippets to send back to the agent."""

    query: str
    files: list[RepoFile]
    content: str
    truncated: bool


def build_repo_map(
    workspace: Path,
    *,
    path: str = ".",
    query: str = "",
    max_files: int = 80,
) -> list[RepoFile]:
    """Scan a workspace and return ranked file summaries."""

    root = _resolve_workspace_path(workspace, path)
    files: list[RepoFile] = []
    query_terms = _query_terms(query)

    for file_path in _iter_candidate_files(root):
        try:
            relative = str(file_path.relative_to(workspace.resolve()))
        except ValueError:
            continue
        file_info = _inspect_file(file_path, relative=relative, query_terms=query_terms)
        files.append(file_info)

    files.sort(key=lambda item: (-item.score, item.path))
    return files[:max_files]


def format_repo_map(files: list[RepoFile]) -> str:
    """Render repo map entries as compact text for the model."""

    if not files:
        return "No files found."

    lines: list[str] = []
    for item in files:
        lines.append(
            f"{item.path} | lang={item.language} | lines={item.line_count} | "
            f"score={item.score} | symbols={', '.join(item.symbols[:8]) or '-'}"
        )
        if item.imports:
            lines.append(f"  imports: {', '.join(item.imports[:8])}")
    return "\n".join(lines)


def build_context_pack(
    workspace: Path,
    *,
    query: str,
    path: str = ".",
    max_files: int = 8,
    max_chars: int = 30_000,
) -> ContextPack:
    """Build a compact context pack from the highest-ranked relevant files."""

    selected = build_repo_map(workspace, path=path, query=query, max_files=max_files)
    chunks: list[str] = []
    used = 0
    truncated = False

    for item in selected:
        file_path = workspace.resolve() / item.path
        header = f"\n--- FILE: {item.path} ({item.language}, {item.line_count} lines) ---\n"
        try:
            body = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            body = f"<could not read: {exc}>\n"

        remaining = max_chars - used - len(header)
        if remaining <= 0:
            truncated = True
            break
        if len(body) > remaining:
            body = body[:remaining] + "\n... truncated ...\n"
            truncated = True
        chunks.append(header + body)
        used += len(header) + len(body)
        if used >= max_chars:
            truncated = True
            break

    return ContextPack(query=query, files=selected, content="".join(chunks).lstrip(), truncated=truncated)


def format_context_pack(pack: ContextPack) -> str:
    """Render a context pack as text for the model."""

    header = [
        f"query: {pack.query}",
        f"files: {len(pack.files)}",
        f"truncated: {str(pack.truncated).lower()}",
        "",
        format_repo_map(pack.files),
        "",
        pack.content,
    ]
    return "\n".join(header).rstrip()


def _inspect_file(file_path: Path, *, relative: str, query_terms: set[str]) -> RepoFile:
    text = file_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    symbols = _extract_symbols(lines)
    imports = _extract_imports(lines)
    language = LANGUAGE_BY_SUFFIX.get(file_path.suffix.lower(), file_path.suffix.lower().lstrip(".") or "text")
    score = _score_file(relative=relative, text=text, symbols=symbols, imports=imports, query_terms=query_terms)
    return RepoFile(
        path=relative,
        language=language,
        size_bytes=file_path.stat().st_size,
        line_count=len(lines),
        symbols=symbols,
        imports=imports,
        score=score,
    )


def _extract_symbols(lines: list[str], *, limit: int = 30) -> list[str]:
    found: list[str] = []
    for line in lines:
        for pattern in SYMBOL_PATTERNS:
            match = pattern.search(line)
            if match:
                found.append(match.group(1))
                break
        if len(found) >= limit:
            break
    return found


def _extract_imports(lines: list[str], *, limit: int = 30) -> list[str]:
    found: list[str] = []
    for line in lines[:300]:
        for pattern in IMPORT_PATTERNS:
            match = pattern.search(line)
            if match:
                value = match.group(1).strip()
                if value and value not in found:
                    found.append(value)
                break
        if len(found) >= limit:
            break
    return found


def _score_file(
    *,
    relative: str,
    text: str,
    symbols: list[str],
    imports: list[str],
    query_terms: set[str],
) -> int:
    if not query_terms:
        return 0

    haystacks = {
        "path": relative.lower(),
        "symbols": " ".join(symbols).lower(),
        "imports": " ".join(imports).lower(),
        "text": text.lower(),
    }
    score = 0
    for term in query_terms:
        if term in haystacks["path"]:
            score += 20
        if term in haystacks["symbols"]:
            score += 12
        if term in haystacks["imports"]:
            score += 6
        score += min(haystacks["text"].count(term), 10)
    return score


def _query_terms(query: str) -> set[str]:
    return {term.lower() for term in re.findall(r"[A-Za-z0-9_./-]+", query) if len(term) >= 2}


def _iter_candidate_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root] if _is_candidate(root) else []

    files: list[Path] = []
    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in SKIP_DIRS)
        for filename in sorted(filenames):
            file_path = Path(current_root) / filename
            if _is_candidate(file_path):
                files.append(file_path)
    return files


def _is_candidate(path: Path) -> bool:
    if path.suffix.lower() in SKIP_SUFFIXES:
        return False
    if not path.is_file():
        return False
    try:
        chunk = path.read_bytes()[:2048]
    except OSError:
        return False
    return b"\x00" not in chunk


def _resolve_workspace_path(workspace: Path, path: str) -> Path:
    root = workspace.resolve()
    candidate = (root / path).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"Path escapes workspace: {path}")
    return candidate
