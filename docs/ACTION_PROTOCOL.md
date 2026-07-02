# Action protocol

`cagent` uses a small JSON action protocol between the model and the local tool runner.

Every model step should return exactly one JSON object with:

```json
{
  "tool": "repo_map",
  "args": {"query": "relevant topic"},
  "note": "brief reason"
}
```

## Validation

Before a tool is used, cagent validates:

- `tool` exists and is a known tool name
- `args` is an object
- required tool arguments are present
- provided arguments use the expected JSON value type
- unsupported arguments are rejected
- `note`, when present, is a string

## Repair loop

If a model response cannot be parsed or does not match the tool schema, cagent asks the same model for a corrected action. The repair prompt includes:

- the validation error
- the list of valid tools
- the required JSON object shape
- a short excerpt of the previous response

The repair loop is intentionally small and bounded. If the model still cannot produce a valid action, the run fails with an `AgentProtocolError`.

## Why this exists

Small local models sometimes mix prose with JSON, miss required arguments, or invent tool fields. Validation and repair makes the agent loop more stable without adding runtime dependencies.
