# cagent

`cagent` is a small self-hosted coding agent for local or private OpenAI-compatible model backends.

The default target setup is a local CLI talking to a proxied model endpoint, for example:

```text
CLI / workstation
  -> http://127.0.0.1:18080/v1
  -> local or Tailscale proxy
  -> Ollama / llama.cpp / vLLM / LM Studio
  -> Tesla T4 worker
  -> qwen2.5-coder:14b-instruct-q4_K_M
```

## Why this exists

This repo starts with a practical MVP instead of a framework-heavy architecture:

- OpenAI-compatible `/v1/chat/completions` client
- no mandatory cloud dependency
- workspace-scoped file access
- guarded shell execution with timeout
- JSON action loop instead of hidden magic
- copy-paste friendly CLI
- works with Ollama's OpenAI-compatible API

## Recommended first model for a Tesla T4

Use this as the default daily coding model:

```text
qwen2.5-coder:14b-instruct-q4_K_M
```

Use a larger model only as an optional slow reviewer/deep mode. A single Tesla T4 has 16 GB VRAM, so a stable 14B quantized coder model is usually more useful than a larger model that constantly offloads to CPU.

## Install

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
```

## Run a local model endpoint

Example with Ollama:

```bash
ollama pull qwen2.5-coder:14b-instruct-q4_K_M
ollama serve
```

Ollama exposes an OpenAI-compatible API at:

```text
http://127.0.0.1:11434/v1
```

If you already have a Tailscale/local proxy, keep your endpoint as:

```text
http://127.0.0.1:18080/v1
```

## Configure

```bash
export CAGENT_BASE_URL=http://127.0.0.1:18080/v1
export CAGENT_MODEL=qwen2.5-coder:14b-instruct-q4_K_M
```

## Doctor

```bash
cagent doctor --base-url http://127.0.0.1:18080/v1 --model qwen2.5-coder:14b-instruct-q4_K_M
```

## Run

```bash
cagent run --workspace . --goal "Inspect this repo and tell me the next implementation step."
```

With file writes and shell enabled:

```bash
cagent run \
  --workspace . \
  --write \
  --shell \
  --goal "Add a small function and run the tests."
```

## Safety model

The agent is not allowed to access files outside the selected workspace. Shell commands run inside the workspace, have a timeout, and pass through a dangerous-command guard before execution.

This is still a developer tool. Do not run it against production directories or secrets until the approval layer is expanded.

## Roadmap

- [x] MVP CLI
- [x] OpenAI-compatible chat client
- [x] workspace file tools
- [x] shell tool with timeout and guardrails
- [x] doctor command
- [x] tests and CI
- [ ] proper patch tool
- [ ] model router: fast/default/reviewer
- [ ] approval prompts for risky actions
- [ ] repo map and context packer
- [ ] persistent run logs
- [ ] OpenWebUI/Codex integration docs
