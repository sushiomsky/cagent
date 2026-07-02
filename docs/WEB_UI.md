# Local web UI

`cagent serve-web` starts a dependency-free local dashboard for one workspace.

It is intended for project observability and light actions, not for exposing cagent to the internet.

## Start

```bash
cagent serve-web --workspace .
```

Default bind address:

```text
http://127.0.0.1:8765/
```

Custom host/port:

```bash
cagent serve-web --workspace . --host 127.0.0.1 --port 8765
```

## Dashboard sections

The dashboard shows:

- project name, type, goal and next action
- verification status
- task table
- local trust status
- local secret-scan findings
- recent `.cagent-runs` logs

## Actions

The UI currently supports two write actions:

- trust workspace
- generate `FINAL_REPORT.md`

Both actions write only inside the selected workspace.

## JSON status endpoint

```text
GET /api/status
```

Returns project, tasks, verification, trust status, secret findings and recent run logs as JSON.

## Logs

```text
GET /logs
GET /logs?file=<log-file-name>
```

Shows recent `.cagent-runs/*.jsonl` logs in the browser.

## Safety notes

- Bind to `127.0.0.1` by default.
- Do not expose this UI publicly.
- It does not provide arbitrary shell execution.
- It does not bypass command profiles or secret redaction.
- It is meant as a local control/inspection surface for a trusted developer machine.
