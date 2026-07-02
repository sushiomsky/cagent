# cagent

`cagent` is a small self-hosted coding and project agent for local or private OpenAI-compatible model backends.

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
- guarded shell execution with timeout and command profiles
- repo map and context pack tools
- project wizard/bootstrapper with `.cagent` state
- task board, tool registry, research notes, artifacts and final reports
- local run-log viewer and HTML export
- MCP-style capability manifest export
- local secret scanning and default tool-output redaction
- workspace trust metadata
- patch-based edits via `git apply`
- git status/diff review tool
- optional local JSONL run logs
- JSON action loop instead of hidden magic
- copy-paste friendly CLI
- works with Ollama's OpenAI-compatible API

## Documentation

- [Client integration guide](docs/CLIENTS.md)
- [Repo map and context packs](docs/REPO_MAP.md)
- [Tesla T4 + Tailscale + Ollama deployment guide](docs/T4_TAILSCALE_OLLAMA.md)
- [Roadmap](docs/ROADMAP.md)

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

For the full worker setup, see [Tesla T4 + Tailscale + Ollama deployment guide](docs/T4_TAILSCALE_OLLAMA.md).

## Configure

```bash
export CAGENT_BASE_URL=http://127.0.0.1:18080/v1
export CAGENT_MODEL=qwen2.5-coder:14b-instruct-q4_K_M
export CAGENT_FAST_MODEL=qwen2.5-coder:7b-instruct-q4_K_M
export CAGENT_REVIEWER_MODEL=qwen3-coder:30b-a3b-q4_K_M
export CAGENT_MODEL_ROLE=default
export CAGENT_COMMAND_PROFILE=inspect
export CAGENT_AUTO_APPROVE_SHELL=0
export CAGENT_REDACT_SECRETS=1
```

Choose a model profile per run:

```bash
cagent run --model-role fast --workspace . --goal "Inspect the repo quickly."
cagent run --model-role reviewer --workspace . --goal "Review the current diff."
```

Choose a shell command policy profile per run:

```bash
cagent run --shell --command-profile inspect --goal "Inspect git status."
cagent run --shell --command-profile test --goal "Discover and run tests."
cagent run --shell --command-profile edit --auto-approve-shell --goal "Format changed files."
```

Command profiles:

- `inspect`: read-only inspection commands such as `ls`, `rg`, `git status`
- `test`: inspection plus common test commands such as `pytest`, `npm test`, `go test`
- `edit`: local write-capable commands require `--auto-approve-shell`
- `network`: network/dependency commands require `--auto-approve-shell`
- `deploy`: broadest profile, still blocks absolute safety patterns

## Security guardrails

Likely secrets are redacted from tool output before it is sent back to the model. Disable this only for a reviewed one-off run:

```bash
cagent run --workspace . --no-redact-secrets --goal "Inspect this file exactly."
```

Scan a workspace locally:

```bash
cagent secret-scan --workspace .
cagent secret-scan --workspace . --fail-on-findings
```

Mark a workspace as reviewed/trusted:

```bash
cagent trust --workspace . --reason "Reviewed repo and local policies."
cagent trust --workspace . --status
```

## Run logs

```bash
export CAGENT_LOG_RUNS=1
```

Logs are written to `.cagent-runs/*.jsonl` and may contain model responses, tool arguments and tool output.

Inspect logs:

```bash
cagent logs --workspace .
cagent logs --workspace . --latest
cagent logs --workspace . --latest --html run.html
```

Export a capability manifest for future MCP/server adapters:

```bash
cagent mcp-manifest
```

## Project wizard and workflow engine

Create a general project, not only a coding task:

```bash
cagent init-project \
  --workspace ./my-agent-project \
  --name "My Agent Project" \
  --type llm_agent \
  --goal "Build a local tool-using agent that can finish project tasks." \
  --deliverable README.md \
  --deliverable FINAL_REPORT.md \
  --allow-shell \
  --allow-network
```

This creates:

```text
PROJECT_SPEC.md
TASKS.md
WORKFLOW.md
AGENTS.md
FINAL_REPORT.md       # generated later
.cagent/project.json
.cagent/tasks.json
.cagent/workflow.json
.cagent/tools.json
.cagent/artifacts.json
.cagent/decisions.jsonl
```

Continue work from project state:

```bash
cagent resume --workspace ./my-agent-project
cagent loop --workspace ./my-agent-project --write --shell --command-profile test
cagent task --workspace ./my-agent-project --id T001 --status verified
cagent tool --workspace ./my-agent-project --name ripgrep --purpose "Fast text search" --status available
cagent research --workspace ./my-agent-project --topic "Model choice" --source manual --summary "14B coder is default."
cagent verify --workspace ./my-agent-project
cagent final-report --workspace ./my-agent-project --notes "Ready for review."
```

## Doctor

```bash
cagent doctor --base-url http://127.0.0.1:18080/v1 --model-role default
```

The doctor command shows the selected role, selected model, configured profiles, command profile, redaction setting, trust status and models reported by the endpoint.

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
  --command-profile test \
  --log-run \
  --goal "Add a small function and run the tests."
```

For client-specific setup, see [Client integration guide](docs/CLIENTS.md).

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

For non-trivial repos the agent should start with `repo_map` or `context_pack` instead of reading many files blindly. Python files use standard-library AST parsing for classes, methods, functions, async functions and imports, with a regex fallback for incomplete files. Other languages still use dependency-free regex heuristics. See [Repo map and context packs](docs/REPO_MAP.md).

## Safety model

The agent is not allowed to access files outside the selected workspace. Shell commands run inside the workspace, have a timeout, and pass through the selected command profile before execution.

Patch application uses `git apply --check` before changing files. File writes and patch application require `--write`. Shell commands require `--shell`. Commands classified as approval-required are blocked unless `--auto-approve-shell` is set after reviewing the command.

This is still a developer tool. Do not run it against production directories or secrets until the approval layer is expanded further.

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
- [x] approval and command profiles for shell actions
- [x] client integration docs
- [x] Tailscale/Ollama/T4 deployment guide
- [x] project wizard/bootstrapper
- [x] persistent task state and resume loop
- [x] tool registry, research notes, verification and final report
- [x] run-log viewer and MCP-style manifest export
- [x] local secret scanning, redaction and workspace trust
