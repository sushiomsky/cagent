# cagent roadmap

## Phase 1: MVP agent loop

Status: implemented in `bootstrap/mvp-agent`.

- CLI entrypoint
- OpenAI-compatible model client
- workspace-scoped file tools
- guarded shell execution
- JSON action protocol
- tests and GitHub Actions CI

## Phase 2: Better code editing

- Add an `apply_patch` tool instead of rewriting full files for every edit.
- Add a structured `git_diff` tool.
- Add automatic test command discovery.
- Add formatting/lint command discovery.
- Add run logs in `.cagent-runs/`.

## Phase 3: Context packing

- Build a repo map from filenames, imports, symbols and recent diffs.
- Add token-budgeted context packs.
- Add ignore rules for generated files, vendored files and large assets.
- Add a short persistent task memory per workspace.

## Phase 4: Model router

- Default model: fast coding model, for example `qwen2.5-coder:14b-instruct-q4_K_M`.
- Reviewer model: larger/slower model for planning and final code review.
- Optional cloud fallback via OpenAI-compatible config only; no hard dependency.

## Phase 5: Approval and safety

- Add interactive approval for risky shell commands.
- Add command profiles: inspect, test, edit, network, deploy.
- Add secret detection before sending context to the model.
- Add read-only mode as the default for unknown workspaces.

## Phase 6: Integrations

- OpenWebUI tool/server mode.
- Codex/OpenCode-compatible endpoint documentation.
- Tailscale/Ollama deployment guide for Tesla T4 workers.
- Simple web UI for run logs and approvals.
