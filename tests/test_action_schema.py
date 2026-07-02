import json
from pathlib import Path

from cagent.action_schema import build_action_repair_prompt, validate_action
from cagent.agent import CodingAgent
from cagent.config import AgentConfig
from cagent.llm import ChatMessage


def test_validate_action_accepts_known_tool_args():
    action = {"tool": "read_file", "args": {"path": "README.md", "start_line": 1}, "note": "read docs"}

    assert validate_action(action) == []


def test_validate_action_rejects_missing_required_arg():
    action = {"tool": "read_file", "args": {}, "note": "read docs"}

    errors = validate_action(action)

    assert any("missing required arg" in item for item in errors)


def test_validate_action_rejects_unknown_arg():
    action = {"tool": "discover_tests", "args": {"path": "."}, "note": "tests"}

    errors = validate_action(action)

    assert any("does not support arg" in item for item in errors)


def test_repair_prompt_mentions_error_and_previous_response():
    prompt = build_action_repair_prompt(error="args need review", raw_response="previous text")

    assert "args need review" in prompt
    assert "previous text" in prompt
    assert "corrected JSON object" in prompt


def test_agent_repairs_invalid_action_before_execution(tmp_path: Path):
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    config = AgentConfig.from_values(workspace=tmp_path, max_steps=1)
    agent = CodingAgent(config)
    first = json.dumps({"tool": "read_file", "args": {}, "note": "needs repair"})
    second = json.dumps({"tool": "read_file", "args": {"path": "README.md"}, "note": "fixed"})
    agent.client = FakeClient([first, second])

    result = agent.run("Read the README")

    assert len(result.steps) == 1
    assert result.steps[0].tool == "read_file"
    assert result.steps[0].ok
    assert "Demo" in result.steps[0].output
    assert agent.client.calls == 2


class FakeClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls = 0

    def complete(
        self,
        *,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int,
    ) -> str:
        self.calls += 1
        assert messages
        assert isinstance(temperature, float)
        assert isinstance(max_tokens, int)
        return self.responses.pop(0)
