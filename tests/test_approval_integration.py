from types import SimpleNamespace

from cagent.approval_queue import list_approval_requests
from cagent import tools as tools_module
from cagent.tools import WorkspaceTools


def test_run_shell_approval_decision_creates_queue_entry(tmp_path, monkeypatch):
    monkeypatch.setattr(
        tools_module,
        "evaluate_command",
        lambda command, profile: SimpleNamespace(
            blocked=False,
            requires_approval=True,
            profile=profile,
            reason="review required by test policy",
            level="approval",
        ),
    )
    workspace_tools = WorkspaceTools(
        workspace=tmp_path,
        allow_write=False,
        allow_shell=True,
        dry_run=False,
        shell_timeout_seconds=5,
        command_profile="edit",
        auto_approve_shell=False,
    )

    result = workspace_tools.run_shell(command="review-me")

    requests = list_approval_requests(tmp_path, status="pending")
    assert not result.ok
    assert "Created approval request" in result.output
    assert len(requests) == 1
    assert requests[0].action_type == "shell"
    assert requests[0].command == "review-me"
    assert requests[0].payload["profile"] == "edit"  # type: ignore[index]
    assert requests[0].payload["tool"] == "run_shell"  # type: ignore[index]


def test_run_shell_blocked_decision_does_not_create_queue_entry(tmp_path, monkeypatch):
    monkeypatch.setattr(
        tools_module,
        "evaluate_command",
        lambda command, profile: SimpleNamespace(
            blocked=True,
            requires_approval=False,
            profile=profile,
            reason="blocked by test policy",
            level="blocked",
        ),
    )
    workspace_tools = WorkspaceTools(
        workspace=tmp_path,
        allow_write=False,
        allow_shell=True,
        dry_run=False,
        shell_timeout_seconds=5,
        command_profile="edit",
        auto_approve_shell=False,
    )

    result = workspace_tools.run_shell(command="blocked-by-test")

    assert not result.ok
    assert "Blocked by command profile" in result.output
    assert list_approval_requests(tmp_path, status="all") == []
