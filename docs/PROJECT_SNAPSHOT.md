# Project snapshot

`cagent.project_snapshot` stores a compact local snapshot under `.cagent/snapshot.json`.

The snapshot contains:

- count
- action
- result
- steps
- log path
- update timestamp

Python helpers:

```python
from pathlib import Path
from cagent.project_snapshot import load_snapshot, save_snapshot

snapshot = save_snapshot(Path("."), action="T001", result="done", steps=1)
print(snapshot.count)
print(load_snapshot(Path(".")))
```

This is a small building block for project review and future status views.
