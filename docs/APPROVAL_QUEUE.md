# Approval queue

`cagent approval` manages a local JSONL approval queue in one workspace.

The queue is meant for risky or irreversible actions that should be reviewed before execution, such as local command execution, file writes, network access, dependency installs or deploy steps.

## Storage

```text
.cagent/approvals.jsonl
```

Every state change appends a new event-like row. The latest row for an approval ID is the current state.

## Automatic requests from agent tools

When `WorkspaceTools.run_shell` receives a policy decision that requires approval and `--auto-approve-shell` is not set, it creates a pending approval request instead of only returning an error.

The request stores:

```text
id
status
action_type
reason
command
policy profile
policy level
tool name
```

The agent can continue with a clear status message, and the user can review the pending item with:

```bash
cagent approval list --workspace .
```

## Create a manual request

```bash
cagent approval request \
  --workspace . \
  --type shell \
  --title "Review action" \
  --reason "Needed for the current task" \
  --command "review-me"
```

Optional payload:

```bash
cagent approval request \
  --workspace . \
  --type network \
  --title "Review external lookup" \
  --reason "Research current tool behavior" \
  --payload '{"url":"https://example.test/docs"}'
```

## List requests

```bash
cagent approval list --workspace .
cagent approval list --workspace . --status all
cagent approval list --workspace . --status handled
cagent approval list --workspace . --json
```

Status values:

```text
pending
approved
rejected
handled
all
```

## Approve or reject

```bash
cagent approval approve --workspace . <approval-id> --note "Looks safe."
cagent approval reject --workspace . <approval-id> --note "Too broad."
```

## Plan approved requests

`approval plan` shows approved requests that are ready for manual handling. It does not execute anything.

```bash
cagent approval plan --workspace .
cagent approval plan --workspace . --id <approval-id>
cagent approval plan --workspace . --json
```

The plan includes:

```text
id
action type
title
reason
detail
payload
runnable=false
next step
```

## Mark handled

After an approved item has been handled outside cagent or by a future specialized runner, mark it as handled:

```bash
cagent approval handled --workspace . <approval-id> --note "Handled after review."
```

Only approved requests can be marked handled.

## Design notes

This phase connects the durable local queue to the toolflow and adds a non-executing runner foundation. A later phase can add specialized reviewed runners for narrow action types while keeping arbitrary execution out of the default path.
