# cagent roadmap

## Phase 1: MVP agent loop

Status: implemented in `bootstrap/mvp-agent` and merged.

- CLI entrypoint
- OpenAI-compatible model client
- workspace-scoped file tools
- guarded shell execution
- JSON action protocol
- tests and GitHub Actions CI

## Phase 2: Better code editing

Status: implemented in `phase2/patch-diff-logs` and merged.

- Add an `apply_patch` tool instead of rewriting full files for every edit.
- Add a structured `git_diff` tool.
- Add automatic test command discovery.
- Add run logs in `.cagent-runs/`.
- Document the new tools and add coverage.

## Phase 3: Context packing

Status: implemented in `phase3/repo-map-context` and merged.

- Build a repo map from filenames, imports and symbols.
- Add char-budgeted context packs.
- Add ignore rules for generated files, vendored files, run logs and large binary assets.
- Add tests and documentation for context selection.

## Phase 4: Model router

Status: implemented in `phase4/model-router` and merged.

- Add default, fast and reviewer model profiles.
- Add CLI flags and environment variables for model roles.
- Make `doctor` show selected role, selected model and all configured profiles.
- Include model role in run logs.
- Add tests and documentation for role resolution.

## Phase 5: Approval and safety

Status: implemented in `phase5/approval-safety`.

- Add command policy profiles: inspect, test, edit, network, deploy.
- Block commands outside the selected profile.
- Require explicit `--auto-approve-shell` for approval-required commands.
- Keep absolute safety patterns blocked even in deploy profile.
- Add CLI/env configuration, tests and documentation.

## Phase 6: Integrations

- OpenWebUI tool/server mode.
- Codex/OpenCode-compatible endpoint documentation.
- Tailscale/Ollama deployment guide for Tesla T4 workers.
- Simple web UI for run logs and approvals.
