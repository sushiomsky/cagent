# Runtime config

`cagent config` prints the resolved runtime configuration without contacting the model endpoint.

Text output:

```bash
cagent config --workspace .
```

JSON output:

```bash
cagent config --workspace . --json
```

Useful checks:

```bash
cagent config --workspace . --model-role fast
cagent config --workspace . --request-retries 3 --retry-backoff-seconds 0.25
cagent config --workspace . --command-profile test
```

This command is useful before `cagent doctor` when the model endpoint may be offline or when you want to verify env/CLI precedence first.
