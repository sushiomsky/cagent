"""Command line interface for cagent."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cagent import __version__
from cagent.agent import AgentProtocolError, CodingAgent
from cagent.config import AgentConfig
from cagent.llm import LLMError, OpenAICompatibleClient


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "doctor":
            return run_doctor(args)
        if args.command == "run":
            return run_agent(args)
    except (LLMError, AgentProtocolError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130

    parser.print_help()
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cagent", description="Small self-hosted coding agent.")
    parser.add_argument("--version", action="version", version=f"cagent {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    doctor = subparsers.add_parser("doctor", help="Check model endpoint and local workspace config.")
    add_common_model_args(doctor)
    doctor.add_argument("--workspace", default=".", help="Workspace path to validate. Default: current directory.")

    run = subparsers.add_parser("run", help="Run the coding agent.")
    add_common_model_args(run)
    run.add_argument("--workspace", default=".", help="Workspace path. Default: current directory.")
    run.add_argument("--goal", help="Goal/task for the agent. Reads stdin when omitted.")
    run.add_argument("--max-steps", type=int, help="Maximum agent tool steps.")
    run.add_argument("--max-tokens", type=int, help="Maximum output tokens per model response.")
    run.add_argument("--write", action="store_true", help="Allow file writes inside the workspace.")
    run.add_argument("--shell", action="store_true", help="Allow guarded shell commands inside the workspace.")
    run.add_argument("--dry-run", action="store_true", help="Show intended writes/commands without executing them.")
    run.add_argument("--show-tool-output", action="store_true", help="Print full tool output after each step.")

    return parser


def add_common_model_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-url", help="OpenAI-compatible base URL. Default: CAGENT_BASE_URL or http://127.0.0.1:18080/v1")
    parser.add_argument("--model", help="Model name. Default: CAGENT_MODEL or qwen2.5-coder:14b-instruct-q4_K_M")
    parser.add_argument("--temperature", type=float, help="Model temperature. Default: 0.15")
    parser.add_argument("--request-timeout", type=int, help="HTTP request timeout in seconds.")
    parser.add_argument("--shell-timeout", type=int, help="Shell command timeout in seconds.")


def run_doctor(args: argparse.Namespace) -> int:
    config = AgentConfig.from_values(
        base_url=args.base_url,
        model=args.model,
        workspace=args.workspace,
        temperature=args.temperature,
        request_timeout_seconds=args.request_timeout,
        shell_timeout_seconds=args.shell_timeout,
    )
    client = OpenAICompatibleClient(
        base_url=config.base_url,
        model=config.model,
        timeout_seconds=config.request_timeout_seconds,
    )
    models = client.list_models()

    print(f"workspace: {config.workspace}")
    print(f"base_url:  {config.base_url}")
    print(f"model:     {config.model}")
    if models:
        print("models:")
        for model in models:
            marker = "*" if model == config.model else "-"
            print(f"  {marker} {model}")
    else:
        print("models: endpoint responded but returned no model IDs")

    if config.model not in models and models:
        print("warning: configured model was not listed by the endpoint", file=sys.stderr)
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
        workspace=Path(args.workspace),
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        max_steps=args.max_steps,
        request_timeout_seconds=args.request_timeout,
        shell_timeout_seconds=args.shell_timeout,
        allow_write=args.write,
        allow_shell=args.shell,
        dry_run=args.dry_run,
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
