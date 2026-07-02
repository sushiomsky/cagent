"""Local run-log viewer utilities."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RunLogSummary:
    path: Path
    run_id: str
    goal: str
    model: str
    model_role: str
    events: int
    finished: bool


def list_run_logs(workspace: Path) -> list[Path]:
    root = workspace / ".cagent-runs"
    if not root.exists():
        return []
    return sorted(root.glob("*.jsonl"), reverse=True)


def summarize_run_log(path: Path) -> RunLogSummary:
    events = read_events(path)
    first = events[0] if events else {}
    payload = first.get("payload", {}) if isinstance(first.get("payload"), dict) else {}
    return RunLogSummary(
        path=path,
        run_id=str(payload.get("run_id", path.stem)),
        goal=str(payload.get("goal", "")),
        model=str(payload.get("model", "")),
        model_role=str(payload.get("model_role", "")),
        events=len(events),
        finished=any(event.get("event") == "finish" for event in events),
    )


def read_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        events.append(json.loads(line))
    return events


def format_summary(summary: RunLogSummary) -> str:
    status = "finished" if summary.finished else "open"
    return (
        f"{summary.path.name}\n"
        f"  status: {status}\n"
        f"  events: {summary.events}\n"
        f"  model:  {summary.model_role or 'default'} / {summary.model}\n"
        f"  goal:   {summary.goal}"
    )


def format_events(path: Path, *, max_events: int = 50) -> str:
    events = read_events(path)
    selected = events[-max_events:]
    lines = [f"# {path.name}", ""]
    for event in selected:
        lines.append(f"## {event.get('event', '<unknown>')} @ {event.get('time', '')}")
        lines.append("")
        lines.append(json.dumps(event.get("payload", {}), indent=2, ensure_ascii=False, sort_keys=True))
        lines.append("")
    return "\n".join(lines)


def render_html(path: Path) -> str:
    events = read_events(path)
    title = html.escape(path.name)
    body = [
        "<!doctype html>",
        "<html><head><meta charset='utf-8'>",
        f"<title>{title}</title>",
        "<style>body{font-family:sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;}pre{background:#f6f8fa;padding:1rem;overflow:auto;}article{border-bottom:1px solid #ddd;padding:1rem 0;}code{font-size:0.9rem;}</style>",
        "</head><body>",
        f"<h1>{title}</h1>",
    ]
    for event in events:
        body.append("<article>")
        body.append(f"<h2>{html.escape(str(event.get('event', '<unknown>')))}</h2>")
        body.append(f"<p><code>{html.escape(str(event.get('time', '')))}</code></p>")
        body.append("<pre>")
        body.append(html.escape(json.dumps(event.get("payload", {}), indent=2, ensure_ascii=False, sort_keys=True)))
        body.append("</pre>")
        body.append("</article>")
    body.append("</body></html>")
    return "\n".join(body)
