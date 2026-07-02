"""Standalone JSON CLI for cagent run logs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cagent.log_viewer import events_json, list_run_logs, summaries_json


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    workspace = Path(args.workspace).resolve()
    logs = list_run_logs(workspace)
    if not logs:
        print("[]")
        return 0

    selected = logs[0] if args.latest else None
    if args.show:
        candidate = Path(args.show)
        selected = candidate if candidate.is_absolute() else workspace / ".cagent-runs" / candidate

    if selected:
        if not selected.exists():
            print(f"error: log file not found: {selected}", file=sys.stderr)
            return 1
        print(events_json(selected, max_events=args.max_events), end="")
        return 0

    print(summaries_json(logs), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cagent-logs-json",
        description="Print cagent run logs as JSON.",
    )
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--show")
    parser.add_argument("--latest", action="store_true")
    parser.add_argument("--max-events", type=int, default=50)
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
