import json

from cagent.approval_queue import create_approval_request, get_approval_request, update_approval_status
from cagent.approval_runner import build_approval_run_plans, format_run_plans, mark_approval_handled, run_plans_json
from cagent.cli import main


def test_build_run_plans_only_returns_approved_requests(tmp_path):
    pending = create_approval_request(
        tmp_path,
        action_type="shell",
        title="Pending action",
        reason="Not ready yet.",
        command="review-me",
    )
    approved = create_approval_request(
        tmp_path,
        action_type="shell",
        title="Approved action",
        reason="Reviewed already.",
        command="review-me-too",
    )
    update_approval_status(tmp_path, approved.id, status="approved", response_note="ok")

    plans = build_approval_run_plans(tmp_path)

    assert [plan.id for plan in plans] == [approved.id]
    assert plans[0].runnable is False
    assert plans[0].detail == "review-me-too"
    assert pending.id not in format_run_plans(plans)


def test_mark_approval_handled_requires_approved_status(tmp_path):
    request = create_approval_request(
        tmp_path,
        action_type="shell",
        title="Pending action",
        reason="Not ready yet.",
        command="review-me",
    )

    try:
        mark_approval_handled(tmp_path, request.id)
    except ValueError as exc:
        assert "must be approved" in str(exc)
    else:  # pragma: no cover - explicit failure path.
        raise AssertionError("expected ValueError")

    update_approval_status(tmp_path, request.id, status="approved", response_note="ok")
    handled = mark_approval_handled(tmp_path, request.id, note="done")

    assert handled.status == "handled"
    assert get_approval_request(tmp_path, request.id).response_note == "done"


def test_run_plans_json_is_machine_readable(tmp_path):
    request = create_approval_request(
        tmp_path,
        action_type="write",
        title="Approved file action",
        reason="Reviewed already.",
        path="README.md",
    )
    update_approval_status(tmp_path, request.id, status="approved", response_note="ok")

    parsed = json.loads(run_plans_json(build_approval_run_plans(tmp_path)))

    assert parsed[0]["id"] == request.id
    assert parsed[0]["runnable"] is False
    assert parsed[0]["detail"] == "README.md"


def test_cli_approval_plan_and_handled(tmp_path, capsys):
    request = create_approval_request(
        tmp_path,
        action_type="shell",
        title="Approved action",
        reason="Reviewed already.",
        command="review-me",
    )
    update_approval_status(tmp_path, request.id, status="approved", response_note="ok")

    code = main(["approval", "plan", "--workspace", str(tmp_path), "--json"])
    assert code == 0
    output = capsys.readouterr().out
    assert request.id in output
    assert '"runnable": false' in output

    code = main(["approval", "handled", "--workspace", str(tmp_path), request.id, "--note", "done"])
    assert code == 0
    assert get_approval_request(tmp_path, request.id).status == "handled"

    code = main(["approval", "list", "--workspace", str(tmp_path), "--status", "handled"])
    assert code == 0
    assert request.id in capsys.readouterr().out
