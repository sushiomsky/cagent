"""Local approval queue for risky cagent actions."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

ApprovalStatus = Literal["pending", "approved", "rejected"]


@dataclass(frozen=True)
class ApprovalRequest:
    id: str
    created_at: str
    updated_at: str
    status: ApprovalStatus
    action_type: str
    title: str
    reason: str
    command: str = ""
    path: str = ""
    payload: dict[str, Any] | None = None
    response_note: str = ""


def approval_path(workspace: Path) -> Path:
    return workspace.resolve() / ".cagent" / "approvals.jsonl"


def create_approval_request(
    workspace: Path,
    *,
    action_type: str,
    title: str,
    reason: str,
    command: str = "",
    path: str = "",
    payload: dict[str, Any] | None = None,
) -> ApprovalRequest:
    now = _now()
    request = ApprovalRequest(
        id=uuid4().hex[:12],
        created_at=now,
        updated_at=now,
        status="pending",
        action_type=action_type,
        title=title,
        reason=reason,
        command=command,
        path=path,
        payload=payload or {},
    )
    _append(workspace, request)
    return request


def list_approval_requests(workspace: Path, *, status: ApprovalStatus | Literal["all"] = "pending") -> list[ApprovalRequest]:
    requests = _read_all(workspace)
    latest: dict[str, ApprovalRequest] = {}
    for request in requests:
        latest[request.id] = request
    values = sorted(latest.values(), key=lambda item: item.created_at)
    if status == "all":
        return values
    return [item for item in values if item.status == status]


def get_approval_request(workspace: Path, request_id: str) -> ApprovalRequest:
    for request in reversed(_read_all(workspace)):
        if request.id == request_id:
            return request
    raise ValueError(f"approval request not found: {request_id}")


def update_approval_status(
    workspace: Path,
    request_id: str,
    *,
    status: ApprovalStatus,
    response_note: str = "",
) -> ApprovalRequest:
    current = get_approval_request(workspace, request_id)
    updated = ApprovalRequest(
        id=current.id,
        created_at=current.created_at,
        updated_at=_now(),
        status=status,
        action_type=current.action_type,
        title=current.title,
        reason=current.reason,
        command=current.command,
        path=current.path,
        payload=current.payload or {},
        response_note=response_note,
    )
    _append(workspace, updated)
    return updated


def format_approval_requests(requests: list[ApprovalRequest]) -> str:
    if not requests:
        return "No approval requests found."
    lines: list[str] = []
    for request in requests:
        lines.append(f"{request.id} [{request.status}] {request.action_type}: {request.title}")
        lines.append(f"  reason: {request.reason}")
        if request.command:
            lines.append(f"  command: {request.command}")
        if request.path:
            lines.append(f"  path: {request.path}")
        if request.response_note:
            lines.append(f"  note: {request.response_note}")
    return "\n".join(lines)


def approvals_json(requests: list[ApprovalRequest]) -> str:
    return json.dumps([asdict(item) for item in requests], indent=2, sort_keys=True) + "\n"


def _append(workspace: Path, request: ApprovalRequest) -> None:
    path = approval_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(request), ensure_ascii=False, sort_keys=True) + "\n")


def _read_all(workspace: Path) -> list[ApprovalRequest]:
    path = approval_path(workspace)
    if not path.exists():
        return []
    requests: list[ApprovalRequest] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            requests.append(ApprovalRequest(**data))
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError(f"invalid approval queue line {line_no}: {exc}") from exc
    return requests


def _now() -> str:
    return datetime.now(UTC).isoformat()
