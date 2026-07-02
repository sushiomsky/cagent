# Client integration guide

`cagent` talks to any backend that exposes an OpenAI-compatible `/v1` API. The intended deployment is simple:

```text
cagent CLI
  -> http://127.0.0.1:18080/v1
  -> local proxy or Tailscale forward
  -> Ollama / llama.cpp / vLLM / LM Studio
  -> coding model
```

## Recommended local endpoint

Use one local endpoint for every tool:

```text
http://127.0.0.1:18080/v1
```

That lets you swap the actual model worker behind the proxy without changing each client.

## cagent CLI

Inspect only:

```bash
cagent doctor \
  --base-url http://127.0.0.1:18080/v1 \
  --model-role default \
  --command-profile inspect

cagent run \
  --workspace . \
  --model-role fast \
  --command-profile inspect \
  --goal "Inspect this repo and summarize the next safe step."
```

Editing with tests:

```bash
cagent run \
  --workspace . \
  --write \
  --shell \
  --command-profile test \
  --log-run \
  --goal "Make the requested change, review the diff, and run tests."
```

Local write-capable shell commands require explicit approval:

```bash
cagent run \
  --workspace . \
  --write \
  --shell \
  --command-profile edit \
  --auto-approve-shell \
  --goal "Format changed files and run tests."
```

## Codex-style clients

For tools that accept an OpenAI-compatible backend, use:

```text
base_url = http://127.0.0.1:18080/v1
model    = qwen2.5-coder:14b-instruct-q4_K_M
```

Recommended local model roles:

```text
fast     = qwen2.5-coder:7b-instruct-q4_K_M
main     = qwen2.5-coder:14b-instruct-q4_K_M
reviewer = qwen3-coder:30b-a3b-q4_K_M
```

Keep the client prompt strict:

```text
You are using a local coding model. Prefer small changes, inspect files before editing, run tests when available, and summarize the final diff.
```

## OpenWebUI

OpenWebUI can use the same local endpoint when configured as an OpenAI-compatible connection.

Suggested values:

```text
API base URL: http://127.0.0.1:18080/v1
Model:        qwen2.5-coder:14b-instruct-q4_K_M
```

Use OpenWebUI for chat/planning and use `cagent` for controlled workspace edits. Keep write actions in `cagent` where command profiles and run logs are available.

## LM Studio / llama.cpp / vLLM

Any backend is fine as long as it serves an OpenAI-compatible API:

```bash
curl http://127.0.0.1:18080/v1/models
```

The response should contain the model ID you want to use. Then verify with:

```bash
cagent doctor --base-url http://127.0.0.1:18080/v1 --model qwen2.5-coder:14b-instruct-q4_K_M
```

## Environment template

```bash
export CAGENT_BASE_URL=http://127.0.0.1:18080/v1
export CAGENT_MODEL=qwen2.5-coder:14b-instruct-q4_K_M
export CAGENT_FAST_MODEL=qwen2.5-coder:7b-instruct-q4_K_M
export CAGENT_REVIEWER_MODEL=qwen3-coder:30b-a3b-q4_K_M
export CAGENT_MODEL_ROLE=default
export CAGENT_COMMAND_PROFILE=inspect
export CAGENT_AUTO_APPROVE_SHELL=0
```

## Troubleshooting

Endpoint does not list models:

```bash
curl -s http://127.0.0.1:18080/v1/models
```

If this fails, fix the backend/proxy first.

Model is listed but responses are slow:

- switch to `--model-role fast`
- reduce `CAGENT_MAX_TOKENS`
- reduce `CAGENT_MAX_STEPS`
- use a smaller context goal

Shell command blocked:

- use `--command-profile test` for tests
- use `--command-profile edit --auto-approve-shell` for local write-capable commands after reviewing the command
- use `--command-profile network --auto-approve-shell` only when network/dependency commands are truly needed
