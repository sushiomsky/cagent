# Local web UI

`cagent serve-web` starts a dependency-free local dashboard for one workspace.

It is intended for project observability and light review actions, not for exposing cagent to the internet.

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
- approval review table
- recent `.cagent-runs` logs

## Actions

The UI supports these local workspace actions:

- trust workspace
- generate `FINAL_REPORT.md`
- approve a pending approval request
- reject a pending approval request

Approval review actions only update `.cagent/approvals.jsonl`. They do not execute the reviewed item.

## Approval review

Pending approval requests appear in the dashboard with action type, title, reason and detail. Each pending row has review buttons for approve/reject.

Use the CLI for the same state:

```bash
cagent approval list --workspace . --status all
```

## JSON status endpoint

```text
GET /api/status
```

Returns project, tasks, verification, trust status, secret findings, approval requests and recent run logs as JSON.

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
- Approval review buttons only change approval state.
- It does not bypass command profiles or secret redaction.
- It is meant as a local control/inspection surface for a trusted developer machine.
