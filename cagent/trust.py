"""Workspace trust metadata for cagent."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TrustInfo:
    workspace: str
    trusted: bool
    reason: str
    created_at: str
    version: int = 1


def trust_path(workspace: Path) -> Path:
    return workspace.resolve() / ".cagent" / "trust.json"


def trust_workspace(workspace: Path, *, reason: str = "User explicitly trusted this workspace.") -> TrustInfo:
    root = workspace.resolve()
    path = trust_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    info = TrustInfo(
        workspace=str(root),
        trusted=True,
        reason=reason,
        created_at=datetime.now(UTC).isoformat(),
    )
    path.write_text(json.dumps(asdict(info), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return info


def load_trust(workspace: Path) -> TrustInfo | None:
    path = trust_path(workspace)
    if not path.exists():
        return None
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return TrustInfo(**data)


def is_trusted(workspace: Path) -> bool:
    info = load_trust(workspace)
    return bool(info and info.trusted and Path(info.workspace).resolve() == workspace.resolve())


def format_trust_status(workspace: Path) -> str:
    info = load_trust(workspace)
    if not info:
        return "Workspace is not trusted yet. Run `cagent trust --workspace . --reason ...` after reviewing it."
    status = "trusted" if is_trusted(workspace) else "not trusted"
    return f"Workspace is {status}: {info.workspace}\nReason: {info.reason}\nCreated: {info.created_at}"
