"""Command line interface for cagent."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from cagent import __version__
from cagent.agent import AgentProtocolError, CodingAgent
from cagent.approval_queue import (
    approvals_json,
    create_approval_request,
    format_approval_requests,
    list_approval_requests,
    update_approval_status,
)
from cagent.approval_runner import build_approval_run_plans, format_run_plans, mark_approval_handled, run_plans_json
from cagent.command_policy import VALID_COMMAND_PROFILES
from cagent.config import AgentConfig
from cagent.llm import LLMError, OpenAICompatibleClient
from cagent.log_viewer import format_events, format_summary, list_run_logs, render_html, summarize_run_log
from cagent.mcp_manifest import manifest_json
from cagent.model_router import VALID_MODEL_ROLES
from cagent.project_engine import (
    PROJECT_TYPES,
    ToolItem,
    add_research_note,
    add_tool,
    create_project,
    load_project,
    next_action,
    update_task_status,
    verify_project,
    write_final_report,
)
from cagent.project_snapshot import format_snapshot, load_snapshot, save_snapshot
from cagent.secret_scan import format_findings, scan_workspace
from cagent.stdio_server import serve_stdio
from cagent.trust import format_trust_status, trust_workspace
from cagent.web_ui import DEFAULT_HOST, DEFAULT_PORT, serve_web_ui


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            return run_doctor(args)
        if args.command == "config":
            return run_config(args)
        if args.command == "run":
            return run_agent(args)
        if args.command == "init-project":
            return run_init_project(args)
        if args.command == "resume":
            return run_resume(args)
        if args.command == "loop":
            return run_project_loop(args)
        if args.command == "snapshot":
            return run_snapshot(args)
        if args.command == "task":
            return run_task(args)
        if args.command == "tool":
            return run_tool(args)
        if args.command == "research":
            return run_research(args)
        if args.command == "verify":
            return run_verify(args)
        if args.command == "final-report":
            return run_final_report(args)
        if args.command == "logs":
            return run_logs(args)
        if args.command == "secret-scan":
            return run_secret_scan(args)
        if args.command == "trust":
            return run_trust(args)
        if args.command == "approval":
            return run_approval(args)
        if args.command == "serve-stdio":
            return serve_stdio()
        if args.command == "serve-web":
            return serve_web_ui(workspace=Path(args.workspace), host=args.host, port=args.port)
        if args.command == "mcp-manifest":
            return run_mcp_manifest()
    except (LLMError, AgentProtocolError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
    parser.print_help()
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cagent", description="Small self-hosted coding/project agent.")
    parser.add_argument("--version", action="version", version=f"cagent {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    doctor = subparsers.add_parser("doctor", help="Check model endpoint and local workspace config.")
    add_common_model_args(doctor)
    add_common_safety_args(doctor)
    doctor.add_argument("--workspace", default=".")

    config = subparsers.add_parser("config", help="Show resolved runtime config without contacting the model endpoint.")
    add_common_model_args(config)
    add_common_safety_args(config)
    config.add_argument("--workspace", default=".")
    config.add_argument("--json", action="store_true")

    run = subparsers.add_parser("run", help="Run the coding agent.")
    add_common_model_args(run)
    add_common_safety_args(run)
    run.add_argument("--workspace", default=".")
    run.add_argument("--goal")
    run.add_argument("--max-steps", type=int)
    run.add_argument("--max-tokens", type=int)
    run.add_argument("--write", action="store_true")
    run.add_argument("--shell", action="store_true")
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--log-run", action="store_true", default=None)
    run.add_argument("--show-tool-output", action="store_true")

    init = subparsers.add_parser("init-project", help="Create project spec, workflow, tasks, tools and hooks.")
    init.add_argument("--workspace", default=".")
    init.add_argument("--name", required=True)
    init.add_argument("--type", choices=PROJECT_TYPES, default="software_project")
    init.add_argument("--goal", required=True)
    init.add_argument("--deliverable", action="append", dest="deliverables")
    init.add_argument("--done", action="append", dest="definition_of_done")
    init.add_argument("--constraint", action="append", dest="constraints")
    init.add_argument("--allow-shell", action="store_true")
    init.add_argument("--allow-network", action="store_true")
    init.add_argument("--allow-tool-install", action="store_true")
    init.add_argument("--no-git", action="store_true")
    init.add_argument("--no-hooks", action="store_true")

    resume = subparsers.add_parser("resume", help="Show the next project action from .cagent state.")
    resume.add_argument("--workspace", default=".")

    loop = subparsers.add_parser("loop", help="Run one project-loop iteration against the next task.")
    add_common_model_args(loop)
    add_common_safety_args(loop)
    loop.add_argument("--workspace", default=".")
    loop.add_argument("--max-steps", type=int, default=8)
    loop.add_argument("--write", action="store_true")
    loop.add_argument("--shell", action="store_true")
    loop.add_argument("--log-run", action="store_true", default=None)
    loop.add_argument("--show-tool-output", action="store_true")

    snapshot = subparsers.add_parser("snapshot", help="Show the latest project snapshot.")
    snapshot.add_argument("--workspace", default=".")

    task = subparsers.add_parser("task", help="Update project task state.")
    task.add_argument("--workspace", default=".")
    task.add_argument("--id", required=True)
    task.add_argument("--status", required=True)
    task.add_argument("--notes", default="")

    tool = subparsers.add_parser("tool", help="Register a project tool in .cagent/tools.json.")
    tool.add_argument("--workspace", default=".")
    tool.add_argument("--name", required=True)
    tool.add_argument("--purpose", required=True)
    tool.add_argument("--status", default="planned")
    tool.add_argument("--install-command", default="")
    tool.add_argument("--risk", default="project")
    tool.add_argument("--notes", default="")

    research = subparsers.add_parser("research", help="Add a structured research note.")
    research.add_argument("--workspace", default=".")
    research.add_argument("--topic", required=True)
    research.add_argument("--source", default="Manual note")
    research.add_argument("--summary", required=True)
    research.add_argument("--decision", default="")

    verify = subparsers.add_parser("verify", help="Verify project scaffolding and task state.")
    verify.add_argument("--workspace", default=".")

    final_report = subparsers.add_parser("final-report", help="Generate FINAL_REPORT.md from project state.")
    final_report.add_argument("--workspace", default=".")
    final_report.add_argument("--notes", default="")

    logs = subparsers.add_parser("logs", help="List, show or render local .cagent-runs logs.")
    logs.add_argument("--workspace", default=".")
    logs.add_argument("--show")
    logs.add_argument("--latest", action="store_true")
    logs.add_argument("--max-events", type=int, default=50)
    logs.add_argument("--html")

    secret_scan = subparsers.add_parser("secret-scan", help="Scan workspace files for likely secrets.")
    secret_scan.add_argument("--workspace", default=".")
    secret_scan.add_argument("--max-files", type=int, default=1000)
    secret_scan.add_argument("--fail-on-findings", action="store_true")

    trust = subparsers.add_parser("trust", help="Trust or inspect trust status for a workspace.")
    trust.add_argument("--workspace", default=".")
    trust.add_argument("--status", action="store_true")
    trust.add_argument("--reason", default="User explicitly trusted this workspace.")

    approval = subparsers.add_parser("approval", help="Manage local approval requests.")
    approval_sub = approval.add_subparsers(dest="approval_command")

    approval_request = approval_sub.add_parser("request", help="Create a pending approval request.")
    approval_request.add_argument("--workspace", default=".")
    approval_request.add_argument("--type", dest="action_type", required=True)
    approval_request.add_argument("--title", required=True)
    approval_request.add_argument("--reason", required=True)
    approval_request.add_argument("--command", dest="request_command", default="")
    approval_request.add_argument("--path", default="")
    approval_request.add_argument("--payload", default="{}")

    approval_list = approval_sub.add_parser("list", help="List approval requests.")
    approval_list.add_argument("--workspace", default=".")
    approval_list.add_argument("--status", choices=("pending", "approved", "rejected", "handled", "all"), default="pending")
    approval_list.add_argument("--json", action="store_true")

    approval_plan = approval_sub.add_parser("plan", help="Show non-executing handling plans for approved requests.")
    approval_plan.add_argument("--workspace", default=".")
    approval_plan.add_argument("--id")
    approval_plan.add_argument("--json", action="store_true")

    approval_approve = approval_sub.add_parser("approve", help="Mark an approval request as approved.")
    approval_approve.add_argument("--workspace", default=".")
    approval_approve.add_argument("id")
    approval_approve.add_argument("--note", default="")

    approval_reject = approval_sub.add_parser("reject", help="Mark an approval request as rejected.")
    approval_reject.add_argument("--workspace", default=".")
    approval_reject.add_argument("id")
    approval_reject.add_argument("--note", default="")

    approval_handled = approval_sub.add_parser("handled", help="Mark an approved request as handled after review.")
    approval_handled.add_argument("--workspace", default=".")
    approval_handled.add_argument("id")
    approval_handled.add_argument("--note", default="Handled after review.")

    serve_web = subparsers.add_parser("serve-web", help="Run the local dependency-free cagent web UI.")
    serve_web.add_argument("--workspace", default=".")
    serve_web.add_argument("--host", default=DEFAULT_HOST)
    serve_web.add_argument("--port", type=int, default=DEFAULT_PORT)
    subparsers.add_parser("serve-stdio", help="Run the local line-delimited JSON-RPC stdio adapter.")
    subparsers.add_parser("mcp-manifest", help="Print a JSON manifest of cagent capabilities.")
    return parser


def add_common_model_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-url")
    parser.add_argument("--model")
    parser.add_argument("--fast-model")
    parser.add_argument("--reviewer-model")
    parser.add_argument("--model-role", choices=VALID_MODEL_ROLES)
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--request-timeout", type=int)
    parser.add_argument("--request-retries", type=int)
    parser.add_argument("--retry-backoff-seconds", type=float)
    parser.add_argument("--shell-timeout", type=int)


def add_common_safety_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--command-profile", choices=VALID_COMMAND_PROFILES)
    parser.add_argument("--auto-approve-shell", action="store_true", default=None)
    parser.add_argument("--no-redact-secrets", action="store_true")


def build_config_from_args(args: argparse.Namespace, *, workspace: str | Path) -> AgentConfig:
    return AgentConfig.from_values(
        base_url=args.base_url,
        model=args.model,
        fast_model=args.fast_model,
        reviewer_model=args.reviewer_model,
        model_role=args.model_role,
        workspace=workspace,
        temperature=args.temperature,
        request_timeout_seconds=args.request_timeout,
        request_retries=args.request_retries,
        retry_backoff_seconds=args.retry_backoff_seconds,
        shell_timeout_seconds=args.shell_timeout,
        command_profile=args.command_profile,
        auto_approve_shell=args.auto_approve_shell,
        redact_secrets=_redact_enabled(args),
    )


def run_doctor(args: argparse.Namespace) -> int:
    config = build_config_from_args(args, workspace=args.workspace)
    print(f"workspace:       {config.workspace}")
    print(f"base_url:        {config.base_url}")
    print(f"model_role:      {config.model_role}")
    print(f"model:           {config.model}")
    print(f"fast_model:      {config.model_profiles.fast}")
    print(f"reviewer_model:  {config.model_profiles.reviewer}")
    print(f"request_retries: {config.request_retries}")
    print(f"retry_backoff:   {config.retry_backoff_seconds}")
    print(f"command_profile: {config.command_profile}")
    print(f"redact_secrets:  {config.redact_secrets}")
    print(format_trust_status(config.workspace))
    try:
        models = OpenAICompatibleClient(
            base_url=config.base_url,
            model=config.model,
            timeout_seconds=config.request_timeout_seconds,
            retries=config.request_retries,
            retry_backoff_seconds=config.retry_backoff_seconds,
        ).list_models()
    except LLMError as exc:
        print(f"models:          unavailable ({exc})")
        return 1
    print("models:")
    for model in models:
        marker = "*" if model == config.model else "-"
        print(f"  {marker} {model}")
    return 0


def run_config(args: argparse.Namespace) -> int:
    config = build_config_from_args(args, workspace=args.workspace)
    payload = config_payload(config)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(format_config_payload(payload))
    return 0


def run_agent(args: argparse.Namespace) -> int:
    goal = args.goal or sys.stdin.read().strip()
    if not goal:
        print("error: provide --goal or stdin", file=sys.stderr)
        return 2
    config = build_config_from_args(args, workspace=args.workspace)
    config = AgentConfig.from_values(
        base_url=config.base_url,
        model=args.model,
        fast_model=args.fast_model,
        reviewer_model=args.reviewer_model,
        model_role=args.model_role,
        workspace=args.workspace,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        max_steps=args.max_steps,
        request_timeout_seconds=args.request_timeout,
        request_retries=args.request_retries,
        retry_backoff_seconds=args.retry_backoff_seconds,
        shell_timeout_seconds=args.shell_timeout,
        command_profile=args.command_profile,
        auto_approve_shell=args.auto_approve_shell,
        redact_secrets=_redact_enabled(args),
        allow_write=args.write,
        allow_shell=args.shell,
        dry_run=args.dry_run,
        log_run=args.log_run,
    )
    if not config.redact_secrets:
        print("warning: secret redaction is disabled for this run", file=sys.stderr)
    result = CodingAgent(config).run(goal)
    for step in result.steps:
        note = f" - {step.note}" if step.note else ""
        print(f"[{step.index}] {step.tool}: {'ok' if step.ok else 'error'}{note}")
        if args.show_tool_output:
            print(step.output)
            print("-" * 80)
    print(result.final_message)
    if result.log_path:
        print(f"run_log: {result.log_path}")
    return 0


def run_init_project(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    spec = create_project(
        root=workspace,
        name=args.name,
        project_type=args.type,
        goal=args.goal,
        deliverables=args.deliverables,
        definition_of_done=args.definition_of_done,
        constraints=args.constraints,
        allow_shell=args.allow_shell,
        allow_network=args.allow_network,
        allow_tool_install=args.allow_tool_install,
        init_git=not args.no_git,
        create_hooks=not args.no_hooks,
    )
    print(f"initialized: {workspace}")
    print(f"project:     {spec.name}")
    print(f"type:        {spec.project_type}")
    print("next:        cagent resume --workspace .")
    return 0


def run_resume(args: argparse.Namespace) -> int:
    print(next_action(Path(args.workspace).resolve()))
    return 0


def run_project_loop(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).resolve()
    spec = load_project(workspace)
    action = next_action(workspace)
    goal = f"Project goal: {spec.goal}\nProject type: {spec.project_type}\nCurrent project-loop action: {action}\nWork on this single next action."
    config = AgentConfig.from_values(
        base_url=args.base_url,
        model=args.model,
        fast_model=args.fast_model,
        reviewer_model=args.reviewer_model,
        model_role=args.model_role,
        workspace=workspace,
        max_steps=args.max_steps,
        temperature=args.temperature,
        request_timeout_seconds=args.request_timeout,
        request_retries=args.request_retries,
        retry_backoff_seconds=args.retry_backoff_seconds,
        shell_timeout_seconds=args.shell_timeout,
        command_profile=args.command_profile,
        auto_approve_shell=args.auto_approve_shell,
        redact_secrets=_redact_enabled(args),
        allow_write=args.write,
        allow_shell=args.shell,
        log_run=args.log_run,
    )
    result = CodingAgent(config).run(goal)
    save_snapshot(
        workspace,
        action=action,
        result=result.final_message,
        steps=len(result.steps),
        log_path=str(result.log_path) if result.log_path else "",
    )
    for step in result.steps:
        print(f"[{step.index}] {step.tool}: {'ok' if step.ok else 'error'}")
        if args.show_tool_output:
            print(step.output)
            print("-" * 80)
    print(result.final_message)
    print(next_action(workspace))
    return 0


def run_snapshot(args: argparse.Namespace) -> int:
    print(format_snapshot(load_snapshot(Path(args.workspace).resolve())))
    return 0


def run_task(args: argparse.Namespace) -> int:
    task = update_task_status(Path(args.workspace).resolve(), args.id, args.status, args.notes)
    print(f"{task.id}: {task.status} - {task.title}")
    return 0


def run_tool(args: argparse.Namespace) -> int:
    item = ToolItem(args.name, args.purpose, args.status, args.install_command, args.risk, args.notes)
    add_tool(Path(args.workspace).resolve(), item)
    print(f"registered tool: {item.name}")
    return 0


def run_research(args: argparse.Namespace) -> int:
    path = add_research_note(
        Path(args.workspace).resolve(),
        topic=args.topic,
        source=args.source,
        summary=args.summary,
        decision=args.decision,
    )
    print(f"research note: {path}")
    return 0


def run_verify(args: argparse.Namespace) -> int:
    result = verify_project(Path(args.workspace).resolve())
    print(f"status: {'PASS' if result.ok else 'NEEDS_WORK'}")
    for item in result.checks:
        print(f"ok: {item}")
    for item in result.warnings:
        print(f"warn: {item}")
    for item in result.missing:
        print(f"missing: {item}")
    return 0 if result.ok else 1


def run_final_report(args: argparse.Namespace) -> int:
    path = write_final_report(Path(args.workspace).resolve(), notes=args.notes)
    print(f"final report: {path}")
    return 0


def run_logs(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).resolve()
    logs = list_run_logs(workspace)
    if not logs:
        print("No run logs found.")
        return 0
    selected = logs[0] if args.latest else None
    if args.show:
        candidate = Path(args.show)
        selected = candidate if candidate.is_absolute() else workspace / ".cagent-runs" / candidate
    if args.html:
        selected = selected or logs[0]
        Path(args.html).write_text(render_html(selected), encoding="utf-8")
        print(f"html: {args.html}")
        return 0
    if selected:
        print(format_events(selected, max_events=args.max_events))
        return 0
    for path in logs:
        print(format_summary(summarize_run_log(path)))
    return 0


def run_secret_scan(args: argparse.Namespace) -> int:
    findings = scan_workspace(Path(args.workspace).resolve(), max_files=args.max_files)
    print(format_findings(findings))
    return 1 if findings and args.fail_on_findings else 0


def run_trust(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).resolve()
    if not args.status:
        trust_workspace(workspace, reason=args.reason)
    print(format_trust_status(workspace))
    return 0


def run_approval(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).resolve()
    command = getattr(args, "approval_command", None)
    if command == "request":
        payload = json.loads(args.payload)
        if not isinstance(payload, dict):
            raise ValueError("--payload must be a JSON object")
        request = create_approval_request(
            workspace,
            action_type=args.action_type,
            title=args.title,
            reason=args.reason,
            command=args.request_command,
            path=args.path,
            payload=payload,
        )
        print(format_approval_requests([request]))
        return 0
    if command == "list":
        requests = list_approval_requests(workspace, status=args.status)
        print(approvals_json(requests) if args.json else format_approval_requests(requests))
        return 0
    if command == "plan":
        plans = build_approval_run_plans(workspace, request_id=args.id)
        print(run_plans_json(plans) if args.json else format_run_plans(plans))
        return 0
    if command == "approve":
        request = update_approval_status(workspace, args.id, status="approved", response_note=args.note)
        print(format_approval_requests([request]))
        return 0
    if command == "reject":
        request = update_approval_status(workspace, args.id, status="rejected", response_note=args.note)
        print(format_approval_requests([request]))
        return 0
    if command == "handled":
        request = mark_approval_handled(workspace, args.id, note=args.note)
        print(format_approval_requests([request]))
        return 0
    print("error: approval requires one of: request, list, plan, approve, reject, handled", file=sys.stderr)
    return 2


def run_mcp_manifest() -> int:
    print(manifest_json(), end="")
    return 0


def config_payload(config: AgentConfig) -> dict[str, Any]:
    return {
        "workspace": str(config.workspace),
        "base_url": config.base_url,
        "model_role": config.model_role,
        "model": config.model,
        "model_profiles": {
            "default": config.model_profiles.default,
            "fast": config.model_profiles.fast,
            "reviewer": config.model_profiles.reviewer,
        },
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "max_steps": config.max_steps,
        "request_timeout_seconds": config.request_timeout_seconds,
        "request_retries": config.request_retries,
        "retry_backoff_seconds": config.retry_backoff_seconds,
        "shell_timeout_seconds": config.shell_timeout_seconds,
        "command_profile": config.command_profile,
        "auto_approve_shell": config.auto_approve_shell,
        "redact_secrets": config.redact_secrets,
        "allow_write": config.allow_write,
        "allow_shell": config.allow_shell,
        "dry_run": config.dry_run,
        "log_run": config.log_run,
    }


def format_config_payload(payload: dict[str, Any]) -> str:
    profiles = payload["model_profiles"]
    lines = [
        f"workspace:               {payload['workspace']}",
        f"base_url:                {payload['base_url']}",
        f"model_role:              {payload['model_role']}",
        f"model:                   {payload['model']}",
        f"fast_model:              {profiles['fast']}",
        f"reviewer_model:          {profiles['reviewer']}",
        f"temperature:             {payload['temperature']}",
        f"max_tokens:              {payload['max_tokens']}",
        f"max_steps:               {payload['max_steps']}",
        f"request_timeout_seconds: {payload['request_timeout_seconds']}",
        f"request_retries:         {payload['request_retries']}",
        f"retry_backoff_seconds:   {payload['retry_backoff_seconds']}",
        f"shell_timeout_seconds:   {payload['shell_timeout_seconds']}",
        f"command_profile:         {payload['command_profile']}",
        f"auto_approve_shell:      {payload['auto_approve_shell']}",
        f"redact_secrets:          {payload['redact_secrets']}",
        f"allow_write:             {payload['allow_write']}",
        f"allow_shell:             {payload['allow_shell']}",
        f"dry_run:                 {payload['dry_run']}",
        f"log_run:                 {payload['log_run']}",
    ]
    return "\n".join(lines)


def _redact_enabled(args: argparse.Namespace) -> bool:
    return not bool(getattr(args, "no_redact_secrets", False))


if __name__ == "__main__":
    raise SystemExit(main())
