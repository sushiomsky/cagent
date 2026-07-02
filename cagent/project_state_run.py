"""Persistent project run state helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class ProjectRunState:
    run_count: int = 0
    current_action: str = ""
    last_result: str = ""
    last_step_count: int = 0
    last_run_log: str = ""
    updated_at: str = ""


def project_run_state_path(workspace: Path) -> Path:
    return workspace.resolve() / ".cagent" / "run-state.json"


def load_project_run_state(workspace: Path) -> ProjectRunState:
    path = project_run_state_path(workspace)
    if not path.exists():
        return ProjectRunState(updated_at=_now())
    data = json.loads(path.read_text(encoding="utf-8"))
    return ProjectRunState(**data)


def record_project_run_state(
    workspace: Path,
    *,
    current_action: str,
    last_result: str,
    last_step_count: int,
    last_run_log: str = "",
) -> ProjectRunState:
    previous = load_project_run_state(workspace)
    state = ProjectRunState(
        run_count=previous.run_count + 1,
        current_action=current_action,
        last_result=last_result,
        last_step_count=last_step_count,
        last_run_log=last_run_log,
        updated_at=_now(),
    )
    path = project_run_state_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(state), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return state


def format_project_run_state(state: ProjectRunState) -> str:
    return "\n".join(
        [
            f"runs: {state.run_count}",
            f"updated_at: {state.updated_at}",
            f"current_action: {state.current_action or '-'}",
            f"last_steps: {state.last_step_count}",
            f"last_result: {state.last_result or '-'}",
            f"last_run_log: {state.last_run_log or '-'}",
        ]
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()
