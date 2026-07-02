# Approval queue

`cagent approval` manages a local JSONL approval queue in one workspace.

The queue is meant for risky or irreversible actions that should be reviewed before execution, such as shell commands, file writes, network access, dependency installs or deploy steps.

## Storage

```text
.cagent/approvals.jsonl
```

Every state change appends a new event-like row. The latest row for an approval ID is the current state.

## Create a request

```bash
cagent approval request \
  --workspace . \
  --type shell \
  --title "Run tests" \
  --reason "Needed to verify the implementation" \
  --command "pytest -q"
```

Optional payload:

```bash
cagent approval request \
  --workspace . \
  --type network \
  --title "Fetch dependency docs" \
  --reason "Research current tool behavior" \
  --payload '{"url":"https://example.test/docs"}'
```

## List requests

```bash
cagent approval list --workspace .
cagent approval list --workspace . --status all
cagent approval list --workspace . --json
```

Status values:

```text
pending
approved
rejected
all
```

## Approve or reject

```bash
cagent approval approve --workspace . <approval-id> --note "Looks safe."
cagent approval reject --workspace . <approval-id> --note "Too broad."
```

## Design notes

This phase adds the durable local queue and CLI. A later phase can make the agent automatically create queue entries when the command policy returns `approval`, and the web UI can expose the queue as an interactive review surface.
