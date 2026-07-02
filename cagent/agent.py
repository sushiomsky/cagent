"""Main agent loop."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cagent.action_schema import build_action_repair_prompt, validate_action
from cagent.config import AgentConfig
from cagent.llm import ChatMessage, OpenAICompatibleClient
from cagent.prompts import SYSTEM_PROMPT, build_goal_prompt
from cagent.runlog import RunLogger
from cagent.tools import WorkspaceTools

MAX_ACTION_REPAIR_ATTEMPTS = 2


@dataclass(frozen=True)
class AgentStep:
    """One executed model action."""

    index: int
    tool: str
    note: str
    ok: bool
    output: str


@dataclass(frozen=True)
class AgentRunResult:
    """Final result returned by the agent loop."""

    final_message: str
    steps: list[AgentStep]
    log_path: Path | None = None


class AgentProtocolError(RuntimeError):
    """Raised when the model does not follow the JSON action protocol."""


class CodingAgent:
    """Small iterative JSON-tool coding agent."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.client = OpenAICompatibleClient(
            base_url=config.base_url,
            model=config.model,
            timeout_seconds=config.request_timeout_seconds,
            retries=config.request_retries,
            retry_backoff_seconds=config.retry_backoff_seconds,
        )
        self.tools = WorkspaceTools(
            workspace=config.workspace,
            allow_write=config.allow_write,
            allow_shell=config.allow_shell,
            dry_run=config.dry_run,
            shell_timeout_seconds=config.shell_timeout_seconds,
            command_profile=config.command_profile,
            auto_approve_shell=config.auto_approve_shell,
            redact_secrets=config.redact_secrets,
        )

    def run(self, goal: str) -> AgentRunResult:
        """Run the agent until it calls `finish` or reaches the step limit."""

        logger = (
            RunLogger(
                workspace=self.config.workspace,
                goal=goal,
                model=self.config.model,
                model_role=self.config.model_role,
                base_url=self.config.base_url,
            )
            if self.config.log_run
            else None
        )
        messages = [
            ChatMessage("system", SYSTEM_PROMPT),
            ChatMessage("user", build_goal_prompt(goal)),
        ]
        steps: list[AgentStep] = []

        for index in range(1, self.config.max_steps + 1):
            raw_response = self.client.complete(
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )
            if logger:
                logger.record("model_response", {"step": index, "raw_response": raw_response})

            action = self._parse_validate_or_repair(
                raw_response=raw_response,
                messages=messages,
                logger=logger,
                step=index,
            )
            tool = str(action.get("tool", "")).strip()
            args = action.get("args") or {}
            note = str(action.get("note", "")).strip()

            if tool == "finish":
                message = str(args.get("message", "Done."))
                if logger:
                    logger.record("finish", {"step": index, "message": message})
                return AgentRunResult(
                    final_message=message,
                    steps=steps,
                    log_path=logger.path if logger else None,
                )

            result = self.tools.execute(tool, args)
            step = AgentStep(
                index=index,
                tool=tool,
                note=note,
                ok=result.ok,
                output=result.output,
            )
            steps.append(step)
            if logger:
                logger.record(
                    "tool_result",
                    {
                        "step": index,
                        "action": action,
                        "ok": result.ok,
                        "output": result.output,
                    },
                )
            messages.append(ChatMessage("assistant", json.dumps(action, ensure_ascii=False)))
            messages.append(ChatMessage("user", result.as_message()))

        final = "Maximum agent steps reached. Re-run with --max-steps if more work is needed."
        if logger:
            logger.record("finish", {"step": self.config.max_steps, "message": final})
        return AgentRunResult(
            final_message=final,
            steps=steps,
            log_path=logger.path if logger else None,
        )

    def _parse_validate_or_repair(
        self,
        *,
        raw_response: str,
        messages: list[ChatMessage],
        logger: RunLogger | None,
        step: int,
    ) -> dict[str, Any]:
        """Parse and validate an action, asking the model to repair bad output."""

        current = raw_response
        for attempt in range(MAX_ACTION_REPAIR_ATTEMPTS + 1):
            try:
                action = parse_action(current)
                errors = validate_action(action)
                if errors:
                    raise AgentProtocolError("; ".join(errors))
                return action
            except AgentProtocolError as exc:
                if attempt >= MAX_ACTION_REPAIR_ATTEMPTS:
                    raise
                repair_prompt = build_action_repair_prompt(error=str(exc), raw_response=current)
                if logger:
                    logger.record(
                        "action_repair",
                        {"step": step, "attempt": attempt + 1, "error": str(exc)},
                    )
                repair_messages = [*messages, ChatMessage("assistant", current), ChatMessage("user", repair_prompt)]
                current = self.client.complete(
                    messages=repair_messages,
                    temperature=0.0,
                    max_tokens=self.config.max_tokens,
                )
                if logger:
                    logger.record(
                        "model_response",
                        {"step": step, "repair_attempt": attempt + 1, "raw_response": current},
                    )
        raise AgentProtocolError("could not repair model action")


def parse_action(raw_response: str) -> dict[str, Any]:
    """Parse the model response as JSON, with a fallback for fenced JSON blocks."""

    text = raw_response.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        try:
            parsed = json.loads(_extract_json_object(text))
        except json.JSONDecodeError as exc:
            raise AgentProtocolError(f"Could not parse JSON action: {exc}") from exc

    if not isinstance(parsed, dict):
        raise AgentProtocolError(f"Model response must be a JSON object: {raw_response}")
    if "tool" not in parsed:
        raise AgentProtocolError(f"Model response missing tool field: {raw_response}")
    return parsed


def _extract_json_object(text: str) -> str:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        return fenced.group(1)

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise AgentProtocolError(f"Could not find JSON object in model response: {text}")
    return text[start : end + 1]
