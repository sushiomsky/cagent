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
- fast/default/reviewer model profiles
- workspace-scoped file access
- guarded shell execution with timeout
- repo map and context pack tools
- patch-based edits via `git apply`
- git status/diff review tool
- optional local JSONL run logs
- JSON action loop instead of hidden magic
- copy-paste friendly CLI
- works with Ollama's OpenAI-compatible API

## Recommended model profiles for a Tesla T4

Use this as the default daily coding model:

```text
qwen2.5-coder:14b-instruct-q4_K_M
```

Use the fast profile for cheaper inspection and short edits:

```text
qwen2.5-coder:7b-instruct-q4_K_M
```

Use the reviewer profile only as an optional slow/deep mode:

```text
qwen3-coder:30b-a3b-q4_K_M
```

A single Tesla T4 has 16 GB VRAM, so a stable 14B quantized coder model is usually more useful as the default than a larger model that constantly offloads to CPU.

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
ollama pull qwen2.5-coder:7b-instruct-q4_K_M
ollama pull qwen3-coder:30b-a3b-q4_K_M
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
export CAGENT_FAST_MODEL=qwen2.5-coder:7b-instruct-q4_K_M
export CAGENT_REVIEWER_MODEL=qwen3-coder:30b-a3b-q4_K_M
export CAGENT_MODEL_ROLE=default
```

Choose a profile per run:

```bash
cagent run --model-role fast --workspace . --goal "Inspect the repo quickly."
cagent run --model-role reviewer --workspace . --goal "Review the current diff."
```

Optional run logs:

```bash
export CAGENT_LOG_RUNS=1
```

Logs are written to `.cagent-runs/*.jsonl` and may contain model responses, tool arguments and tool output.

## Doctor

```bash
cagent doctor --base-url http://127.0.0.1:18080/v1 --model-role default
```

The doctor command shows the selected role, selected model, configured profiles and models reported by the endpoint.

## Run

```bash
cagent run --workspace . --goal "Inspect this repo and tell me the next implementation step."
```

With file writes, shell and run logs enabled:

```bash
cagent run \
  --workspace . \
  --write \
  --shell \
  --log-run \
  --goal "Add a small function and run the tests."
```

## Agent tools

The model can request these tools through the JSON action loop:

- `list_files`: list workspace files
- `repo_map`: ranked repository overview with language, line counts, symbols and imports
- `context_pack`: compact relevant file snippets selected from the repo map
- `read_file`: read a UTF-8 file with optional line range
- `write_file`: write or replace a UTF-8 file
- `apply_patch`: apply a unified diff through `git apply`
- `search_text`: regex/text search in workspace files
- `git_diff`: show `git status --short` and `git diff`
- `discover_tests`: suggest likely test commands
- `run_shell`: run guarded shell commands when `--shell` is enabled
- `finish`: end the run

## Context strategy

For non-trivial repos the agent should start with `repo_map` or `context_pack` instead of reading many files blindly. The first implementation intentionally uses dependency-free regex heuristics rather than AST parsers or Tree-sitter. It detects common symbols and imports across Python, JavaScript/TypeScript, Go, Rust, PHP, shell and config/documentation files.

## Safety model

The agent is not allowed to access files outside the selected workspace. Shell commands run inside the workspace, have a timeout, and pass through a dangerous-command guard before execution.

Patch application uses `git apply --check` before changing files. File writes and patch application require `--write`. Shell commands require `--shell`.

This is still a developer tool. Do not run it against production directories or secrets until the approval layer is expanded.

## Roadmap

- [x] MVP CLI
- [x] OpenAI-compatible chat client
- [x] workspace file tools
- [x] shell tool with timeout and guardrails
- [x] doctor command
- [x] tests and CI
- [x] proper patch tool
- [x] git diff review tool
- [x] optional run logs
- [x] test command discovery
- [x] repo map and context packer
- [x] model router: fast/default/reviewer
- [ ] approval prompts for risky actions
- [ ] OpenWebUI/Codex integration docs
