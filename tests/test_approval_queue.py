import json

from cagent.approval_queue import (
    approvals_json,
    create_approval_request,
    format_approval_requests,
    get_approval_request,
    list_approval_requests,
    update_approval_status,
)
from cagent.cli import main


def test_create_and_list_approval_request(tmp_path):
    request = create_approval_request(
        tmp_path,
        action_type="shell",
        title="Run tests",
        reason="Need to verify changes.",
        command="pytest -q",
    )

    listed = list_approval_requests(tmp_path)

    assert listed == [request]
    assert listed[0].status == "pending"
    assert listed[0].command == "pytest -q"
    assert ".cagent" in str((tmp_path / ".cagent" / "approvals.jsonl"))


def test_update_approval_status_appends_latest_state(tmp_path):
    request = create_approval_request(
        tmp_path,
        action_type="write",
        title="Edit file",
        reason="Needed for task.",
        path="README.md",
    )

    approved = update_approval_status(tmp_path, request.id, status="approved", response_note="Looks safe")

    assert approved.status == "approved"
    assert get_approval_request(tmp_path, request.id).status == "approved"
    assert list_approval_requests(tmp_path, status="pending") == []
    assert list_approval_requests(tmp_path, status="approved") == [approved]


def test_format_and_json_outputs_are_useful(tmp_path):
    request = create_approval_request(
        tmp_path,
        action_type="network",
        title="Fetch docs",
        reason="Research dependency docs.",
        payload={"url": "https://example.test/docs"},
    )

    text = format_approval_requests([request])
    parsed = json.loads(approvals_json([request]))

    assert request.id in text
    assert "Fetch docs" in text
    assert parsed[0]["payload"]["url"] == "https://example.test/docs"


def test_cli_approval_request_list_approve_reject(tmp_path, capsys):
    code = main(
        [
            "approval",
            "request",
            "--workspace",
            str(tmp_path),
            "--type",
            "shell",
            "--title",
            "Run tests",
            "--reason",
            "Verify changes",
            "--command",
            "pytest -q",
        ]
    )
    assert code == 0
    request_id = list_approval_requests(tmp_path)[0].id

    code = main(["approval", "list", "--workspace", str(tmp_path), "--json"])
    assert code == 0
    output = capsys.readouterr().out
    assert request_id in output

    code = main(["approval", "approve", "--workspace", str(tmp_path), request_id, "--note", "ok"])
    assert code == 0
    assert get_approval_request(tmp_path, request_id).status == "approved"

    code = main(["approval", "reject", "--workspace", str(tmp_path), request_id, "--note", "later rejected"])
    assert code == 0
    assert get_approval_request(tmp_path, request_id).status == "rejected"
