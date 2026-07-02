import pytest

from cagent.command_policy import evaluate_command, normalize_command_profile


def test_inspect_profile_allows_read_only_command():
    decision = evaluate_command("git status --short", profile="inspect")

    assert decision.allowed_without_approval
    assert decision.profile == "inspect"


def test_inspect_profile_blocks_test_command():
    decision = evaluate_command("pytest -q", profile="inspect")

    assert decision.blocked
    assert "requires test/edit/network/deploy" in decision.reason


def test_test_profile_allows_test_command():
    decision = evaluate_command("pytest -q", profile="test")

    assert decision.allowed_without_approval


def test_edit_profile_requires_approval_for_write_command():
    decision = evaluate_command("touch generated.txt", profile="edit")

    assert decision.requires_approval
    assert "write-capable" in decision.reason


def test_network_profile_requires_approval_for_curl():
    decision = evaluate_command("curl https://example.com", profile="network")

    assert decision.requires_approval
    assert "network" in decision.reason


def test_inspect_profile_blocks_network_command():
    decision = evaluate_command("curl https://example.com", profile="inspect")

    assert decision.blocked
    assert "network/deploy" in decision.reason


def test_absolute_safety_pattern_blocks_even_deploy_profile():
    decision = evaluate_command("sudo whoami", profile="deploy")

    assert decision.blocked
    assert "absolute safety" in decision.reason


def test_invalid_profile_raises_clear_error():
    with pytest.raises(ValueError, match="Invalid command profile"):
        normalize_command_profile("godmode")
