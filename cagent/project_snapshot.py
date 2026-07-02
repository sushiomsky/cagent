"""Small persistent project snapshot helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class ProjectSnapshot:
    count: int = 0
    action: str = ""
    result: str = ""
    steps: int = 0
    log_path: str = ""
    updated_at: str = ""


def snapshot_path(workspace: Path) -> Path:
    return workspace.resolve() / ".cagent" / "snapshot.json"


def load_snapshot(workspace: Path) -> ProjectSnapshot:
    path = snapshot_path(workspace)
    if not path.exists():
        return ProjectSnapshot(updated_at=_now())
    data = json.loads(path.read_text(encoding="utf-8"))
    return ProjectSnapshot(**data)


def save_snapshot(
    workspace: Path,
    *,
    action: str,
    result: str,
    steps: int,
    log_path: str = "",
) -> ProjectSnapshot:
    previous = load_snapshot(workspace)
    snapshot = ProjectSnapshot(
        count=previous.count + 1,
        action=action,
        result=result,
        steps=steps,
        log_path=log_path,
        updated_at=_now(),
    )
    path = snapshot_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(snapshot), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return snapshot


def format_snapshot(snapshot: ProjectSnapshot) -> str:
    return "\n".join(
        [
            f"count: {snapshot.count}",
            f"updated_at: {snapshot.updated_at}",
            f"action: {snapshot.action or '-'}",
            f"steps: {snapshot.steps}",
            f"result: {snapshot.result or '-'}",
            f"log_path: {snapshot.log_path or '-'}",
        ]
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()
