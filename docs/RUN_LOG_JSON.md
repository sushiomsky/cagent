# Run log JSON helpers

The `cagent.log_viewer` module provides JSON-safe helpers for downstream tools and dashboards.

Available helpers:

```python
from cagent.log_viewer import events_json, summaries_json

print(summaries_json(paths))
print(events_json(path, max_events=50))
```

`summaries_json()` returns a JSON array of run summaries with string paths.

`events_json()` returns the most recent events from a selected JSONL run log.

## CLI

Install the package, then run:

```bash
cagent-logs-json --workspace .
cagent-logs-json --workspace . --latest
cagent-logs-json --workspace . --show run.jsonl --max-events 20
```

This prints JSON to stdout. The standalone command is intentionally small and can be reused by other CLI, web UI or adapter layers later.
