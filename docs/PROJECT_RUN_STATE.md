# Project run state

`cagent` can record a small project run state file for local review.

Location:

```text
.cagent/run-state.json
```

The state includes:

- recorded run count
- current action text
- last result message
- tool step count
- run log path when available
- update timestamp

Show the current state:

```bash
cagent run-state --workspace .
```

This is a local review aid for explicit project commands.
