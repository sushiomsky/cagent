"""Command line interface for cagent."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cagent import __version__
from cagent.agent import AgentProtocolError, CodingAgent
from cagent.command_policy import VALID_COMMAND_PROFILES
from cagent.config import AgentConfig
from cagent.llm import LLMError, OpenAICompatibleClient
from cagent.model_router import VALID_MODEL_ROLES
from cagent.project_engine import (
    PROJECT_TYPES,
    ToolItem,
    add_research_note,
    add_tool,
    create_project,
    load_project,
    load_tasks,
    next_action,
    update_task_status,
    verify_project,
    write_final_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "doctor":
            return run_doctor(args)
        if args.command == "run":
            return run_agent(args)
        if args.command == "init-project":
            return run_init_project(args)
        if args.command == "resume":
            return run_resume(args)
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
        if args.command == "loop":
            return run_project_loop(args)
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
    doctor.add_argument("--workspace", default=".", help="Workspace path to validate. Default: current directory.")

    run = subparsers.add_parser("run", help="Run the coding agent.")
    add_common_model_args(run)
    add_common_safety_args(run)
    run.add_argument("--workspace", default=".", help="Workspace path. Default: current directory.")
    run.add_argument("--goal", help="Goal/task for the agent. Reads stdin when omitted.")
    run.add_argument("--max-steps", type=int, help="Maximum agent tool steps.")
    run.add_argument("--max-tokens", type=int, help="Maximum output tokens per model response.")
    run.add_argument("--write", action="store_true", help="Allow file writes and patch application inside the workspace.")
    run.add_argument("--shell", action="store_true", help="Allow guarded shell commands inside the workspace.")
    run.add_argument("--dry-run", action="store_true", help="Show intended writes/commands without executing them.")
    run.add_argument(
        "--log-run",
        action="store_true",
        default=None,
        help="Write a JSONL run log under .cagent-runs/.",
    )
    run.add_argument("--show-tool-output", action="store_true", help="Print full tool output after each step.")

    init = subparsers.add_parser("init-project", help="Create project spec, workflow, tasks, tools and hooks.")
    init.add_argument("--workspace", default=".", help="Project folder. Created if missing.")
    init.add_argument("--name", required=True, help="Project name.")
    init.add_argument("--type", choices=PROJECT_TYPES, default="software_project", help="Project template type.")
    init.add_argument("--goal", required=True, help="Project goal.")
    init.add_argument("--deliverable", action="append", dest="deliverables", help="Expected deliverable path. Repeatable.")
    init.add_argument("--done", action="append", dest="definition_of_done", help="Definition-of-done item. Repeatable.")
    init.add_argument("--constraint", action="append", dest="constraints", help="Project constraint. Repeatable.")
    init.add_argument("--allow-shell", action="store_true", help="Mark shell usage as allowed in project policy.")
    init.add_argument("--allow-network", action="store_true", help="Mark network research/use as allowed in project policy.")
    init.add_argument("--allow-tool-install", action="store_true", help="Mark project tool installation as allowed.")
    init.add_argument("--no-git", action="store_true", help="Do not initialize git.")
    init.add_argument("--no-hooks", action="store_true", help="Do not create git hooks.")

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

    task = subparsers.add_parser("task", help="Update project task state.")
    task.add_argument("--workspace", default=".")
    task.add_argument("--id", required=True, help="Task id, e.g. T001.")
    task.add_argument("--status", required=True, help="todo|in_progress|blocked|needs_user|done|verified")
    task.add_argument("--notes", default="", help="Optional status note.")

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

    return parser


def add_common_model_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--base-url",
        help="OpenAI-compatible base URL. Default: CAGENT_BASE_URL or http://127.0.0.1:18080/v1",
    )
    parser.add_argument(
        "--model",
        help="Default model profile. Default: CAGENT_MODEL or qwen2.5-coder:14b-instruct-q4_K_M",
    )
    parser.add_argument(
        "--fast-model",
        help="Fast model profile. Default: CAGENT_FAST_MODEL or qwen2.5-coder:7b-instruct-q4_K_M",
    )
    parser.add_argument(
        "--reviewer-model",
        help="Reviewer model profile. Default: CAGENT_REVIEWER_MODEL or qwen3-coder:30b-a3b-q4_K_M",
    )
    parser.add_argument(
        "--model-role",
        choices=VALID_MODEL_ROLES,
        help="Model profile to use for this command. Default: CAGENT_MODEL_ROLE or default.",
    )
    parser.add_argument("--temperature", type=float, help="Model temperature. Default: 0.15")
    parser.add_argument("--request-timeout", type=int, help="HTTP request timeout in seconds.")
    parser.add_argument("--shell-timeout", type=int, help="Shell command timeout in seconds.")


def add_common_safety_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--command-profile",
        choices=VALID_COMMAND_PROFILES,
        help="Shell command policy profile. Default: CAGENT_COMMAND_PROFILE or inspect.",
    )
    parser.add_argument(
        "--auto-approve-shell",
        action="store_true",
        default=None,
        help="Execute approval-required shell commands after the policy allows them.",
    )


def build_config_from_args(args: argparse.Namespace, *, workspace: str | Path) -> AgentConfig:
    """Build AgentConfig from parsed CLI arguments."""

    return AgentConfig.from_values(
        base_url=args.base_url,
        model=args.model,
        fast_model=args.fast_model,
        reviewer_model=args.reviewer_model,
        model_role=args.model_role,
        workspace=workspace,
        temperature=args.temperature,
        request_timeout_seconds=args.request_timeout,
        shell_timeout_seconds=args.shell_timeout,
        command_profile=args.command_profile,
        auto_approve_shell=args.auto_approve_shell,
    )


def run_doctor(args: argparse.Namespace) -> int:
    config = build_config_from_args(args, workspace=args.workspace)
    client = OpenAICompatibleClient(
        base_url=config.base_url,
        model=config.model,
        timeout_seconds=config.request_timeout_seconds,
    )
    models = client.list_models()

    print(f"workspace:       {config.workspace}")
    print(f"base_url:        {config.base_url}")
    print(f"role:            {config.model_role}")
    print(f"model:           {config.model}")
    print(f"command_profile: {config.command_profile}")
    print(f"auto_approve:    {config.auto_approve_shell}")
    print("profiles:")
    for line in config.model_profiles.as_lines(selected_role=config.model_role):
        print(line)
    if models:
        print("models:")
        for model in models:
            marker = "*" if model == config.model else "-"
            print(f"  {marker} {model}")
    else:
        print("models: endpoint responded but returned no model IDs")

    if config.model not in models and models:
        print("warning: selected model was not listed by the endpoint", file=sys.stderr)
        return 1
    return 0


def run_agent(args: argparse.Namespace) -> int:
    goal = args.goal if args.goal is not None else sys.stdin.read().strip()
    if not goal:
        print("error: provide --goal or pipe a goal through stdin", file=sys.stderr)
        return 2

    config = AgentConfig.from_values(
        base_url=args.base_url,
        model=args.model,
        fast_model=args.fast_model,
        reviewer_model=args.reviewer_model,
        model_role=args.model_role,
        workspace=Path(args.workspace),
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        max_steps=args.max_steps,
        request_timeout_seconds=args.request_timeout,
        shell_timeout_seconds=args.shell_timeout,
        command_profile=args.command_profile,
        auto_approve_shell=args.auto_approve_shell,
        allow_write=args.write,
        allow_shell=args.shell,
        dry_run=args.dry_run,
        log_run=args.log_run,
    )

    agent = CodingAgent(config)
    result = agent.run(goal)

    for step in result.steps:
        status = "ok" if step.ok else "error"
        note = f" - {step.note}" if step.note else ""
        print(f"[{step.index}] {step.tool}: {status}{note}")
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
    workspace = Path(args.workspace).resolve()
    print(next_action(workspace))
    return 0


def run_project_loop(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).resolve()
    spec = load_project(workspace)
    action = next_action(workspace)
    goal = (
        f"Project goal: {spec.goal}\n"
        f"Project type: {spec.project_type}\n"
        f"Current project-loop action: {action}\n"
        "Work on this single next action. Update files as needed, use existing project state, "
        "review the diff, and stop with a concise status."
    )
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
        shell_timeout_seconds=args.shell_timeout,
        command_profile=args.command_profile,
        auto_approve_shell=args.auto_approve_shell,
        allow_write=args.write,
        allow_shell=args.shell,
        log_run=args.log_run,
    )
    result = CodingAgent(config).run(goal)
    for step in result.steps:
        print(f"[{step.index}] {step.tool}: {'ok' if step.ok else 'error'}")
        if args.show_tool_output:
            print(step.output)
            print("-" * 80)
    print(result.final_message)
    print(next_action(workspace))
    return 0


def run_task(args: argparse.Namespace) -> int:
    task = update_task_status(Path(args.workspace).resolve(), args.id, args.status, args.notes)
    print(f"{task.id}: {task.status} - {task.title}")
    return 0


def run_tool(args: argparse.Namespace) -> int:
    item = ToolItem(
        name=args.name,
        purpose=args.purpose,
        status=args.status,
        install_command=args.install_command,
        risk=args.risk,
        notes=args.notes,
    )
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


if __name__ == "__main__":
    raise SystemExit(main())
