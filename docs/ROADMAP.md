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

Status: implemented in `phase5/approval-safety` and merged.

- Add command policy profiles: inspect, test, edit, network, deploy.
- Block commands outside the selected profile.
- Require explicit `--auto-approve-shell` for approval-required commands.
- Keep absolute safety patterns blocked even in deploy profile.
- Add CLI/env configuration, tests and documentation.

## Phase 6: Integrations

Status: implemented in `phase6/docs` and merged.

- Add client integration guide for cagent, OpenAI-compatible clients and OpenWebUI.
- Add Tesla T4 + Tailscale + Ollama deployment guide.
- Document local endpoint conventions, model profiles and smoke tests.
- Link integration docs from the README.

## Phase 7: Project wizard and bootstrapper

Status: implemented in `phase7-15/project-engine` and merged.

- Add `cagent init-project` to define a project goal, type, deliverables and definition of done.
- Create `PROJECT_SPEC.md`, `TASKS.md`, `WORKFLOW.md`, `AGENTS.md` and `.cagent/project.json`.
- Initialize project directories, git and lightweight hooks.

## Phase 8: Persistent project state and resume loop

Status: implemented in `phase7-15/project-engine` and merged.

- Add `.cagent/tasks.json`, `.cagent/decisions.jsonl`, `.cagent/artifacts.json` and `.cagent/tools.json`.
- Add `cagent resume`, `cagent task` and `cagent loop`.
- Run one loop iteration against the next project task.

## Phase 9: Tool manager and research notes

Status: implemented in `phase7-15/project-engine` and merged.

- Add `cagent tool` to register planned/available tools.
- Add `cagent research` to create structured notes under `docs/research/`.
- Record decisions as JSONL events.

## Phase 10: Multi-agent workflow roles

Status: implemented in `phase7-15/project-engine` and merged.

- Add `AGENTS.md` and `.cagent/workflow.json`.
- Define planner, researcher, implementer, tester and reviewer roles with model profiles.

## Phase 11: Verification and final reports

Status: implemented in `phase7-15/project-engine` and merged.

- Add `cagent verify` to check required project files and task state.
- Add `cagent final-report` to generate `FINAL_REPORT.md`.

## Phase 12: Observability and adapter foundation

Status: implemented in `phase7-15/project-engine` and merged.

- Add `cagent logs` to list, inspect and HTML-render `.cagent-runs` logs.
- Add `cagent mcp-manifest` as a stable JSON capability manifest for future MCP/server adapters.

## Phase 13: Secret scanning and workspace trust

Status: implemented in `phase13/security-foundation` and merged.

- Add local secret scanning and formatting.
- Redact likely secrets from tool output by default.
- Add `cagent secret-scan` and `cagent trust`.
- Add `.cagent/trust.json` workspace trust metadata.
- Expose security capabilities in the manifest.

## Phase 14: Stdio adapter

Status: implemented in `phase14/stdio-adapter` and merged.

- Add `cagent serve-stdio`.
- Add a line-delimited JSON-RPC adapter with `initialize`, `tools/list`, `tools/call` and `shutdown`.
- Expose conservative project-state tools for resume, verify, secret scan, trust, final report and manifest.
- Add adapter docs and tests.

## Phase 15: Local web UI

Status: implemented in `phase15/web-ui` and merged.

- Add `cagent serve-web`.
- Add a dependency-free local dashboard for project, tasks, verification, security, trust and run logs.
- Add JSON status endpoint and light actions for workspace trust and final report generation.
- Add web UI docs and tests.

## Phase 16: Secret scanning quality

Status: implemented in `phase16/secret-quality` and merged.

- Add severity to findings.
- Add entropy scoring and filtering for noisy placeholder values.
- Add workspace allowlist files.
- Add machine-readable `findings_json` helper.
- Add docs and tests.

## Phase 17: Approval queue

Status: implemented in `phase17/approval-queue` and merged.

- Add durable `.cagent/approvals.jsonl` storage.
- Add `cagent approval request/list/approve/reject`.
- Add text and JSON output for approvals.
- Add docs, manifest entry and tests.

## Phase 18: Approval integration

Status: implemented in `phase18/approval-integration` and merged.

- Make review-required tool policy decisions automatically create queue entries.
- Return the approval request ID to the agent loop.
- Add safer process invocation behavior for reviewed local tool actions.
- Add docs and tests.

## Phase 19: Web approval review

Status: implemented in `phase19/web-approval-review` and merged.

- Show approval requests in `cagent serve-web`.
- Include approvals in `/api/status`.
- Add web buttons to approve or reject pending requests.
- Keep review state changes status-only.
- Add docs and tests.

## Phase 20: Approval runner foundation

Status: implemented in `phase20/approval-runner-foundation` and merged.

- Add status-only plans for approved requests.
- Add `handled` approval status.
- Add `cagent approval plan` and `cagent approval handled`.
- Add docs and tests.

## Phase 21: Web approval plans

Status: implemented in `phase21/web-approval-plans` and merged.

- Show approved handling plans in `cagent serve-web`.
- Include approval plans in `/api/status`.
- Add web action to mark approved requests as handled.
- Keep plan review status-only.
- Add docs and tests.

## Phase 22: Quality gates

Status: implemented in `phase22/quality-gates`.

- Add `ruff` to development dependencies.
- Add root `Makefile` targets for compile, lint, test and full check.
- Run the same full quality gate in GitHub Actions CI.
- Add quality-gate documentation.

## Phase 23: Future improvements

- Full SDK-backed MCP server mode.
- Optional language-specific repo map parsers.
- Add more narrow reviewed status workflows.
