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

These helpers are intentionally in the core module first so CLI, web UI and adapter layers can share the same serialization behavior later.
