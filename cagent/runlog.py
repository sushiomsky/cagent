"""Append-only JSONL run logging for cagent."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class RunLogger:
    """Small JSONL logger for agent runs.

    Logs are intentionally explicit and local. They may contain file snippets, tool
    outputs, model responses and command output, so users should only enable them
    in workspaces where that is acceptable.
    """

    def __init__(
        self,
        *,
        workspace: Path,
        goal: str,
        model: str,
        base_url: str,
        model_role: str = "default",
    ) -> None:
        self.run_id = uuid.uuid4().hex
        self.path = workspace / ".cagent-runs" / f"{_timestamp()}-{self.run_id}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.record(
            "run_start",
            {
                "run_id": self.run_id,
                "goal": goal,
                "model": model,
                "model_role": model_role,
                "base_url": base_url,
            },
        )

    def record(self, event_type: str, payload: dict[str, Any]) -> None:
        """Append one event as a JSON object."""

        event = {
            "time": datetime.now(UTC).isoformat(),
            "event": event_type,
            "payload": _jsonable(payload),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return repr(value)
