"""Main agent loop."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from cagent.config import AgentConfig
from cagent.llm import ChatMessage, OpenAICompatibleClient
from cagent.prompts import SYSTEM_PROMPT, build_goal_prompt
from cagent.tools import ToolResult, WorkspaceTools


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
        )
        self.tools = WorkspaceTools(
            workspace=config.workspace,
            allow_write=config.allow_write,
            allow_shell=config.allow_shell,
            dry_run=config.dry_run,
            shell_timeout_seconds=config.shell_timeout_seconds,
        )

    def run(self, goal: str) -> AgentRunResult:
        """Run the agent until it calls `finish` or reaches the step limit."""

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
            action = parse_action(raw_response)
            tool = str(action.get("tool", "")).strip()
            args = action.get("args") or {}
            note = str(action.get("note", "")).strip()

            if not isinstance(args, dict):
                raise AgentProtocolError(f"Action args must be an object: {action!r}")

            if tool == "finish":
                message = str(args.get("message", "Done."))
                return AgentRunResult(final_message=message, steps=steps)

            result = self.tools.execute(tool, args)
            steps.append(
                AgentStep(
                    index=index,
                    tool=tool,
                    note=note,
                    ok=result.ok,
                    output=result.output,
                )
            )
            messages.append(ChatMessage("assistant", json.dumps(action, ensure_ascii=False)))
            messages.append(ChatMessage("user", result.as_message()))

        final = "Maximum agent steps reached. Re-run with --max-steps if more work is needed."
        return AgentRunResult(final_message=final, steps=steps)


def parse_action(raw_response: str) -> dict[str, Any]:
    """Parse the model response as JSON, with a fallback for fenced JSON blocks."""

    text = raw_response.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = json.loads(_extract_json_object(text))

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
