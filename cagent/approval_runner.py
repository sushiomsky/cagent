"""Reviewed approval runner foundation.

This module deliberately does not execute arbitrary approved requests. It builds
clear run plans for approved approval-queue items and can mark reviewed items as
handled after the user has dealt with them externally or through a future
specialized runner.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from cagent.approval_queue import ApprovalRequest, get_approval_request, list_approval_requests, update_approval_status


@dataclass(frozen=True)
class ApprovalRunPlan:
    id: str
    action_type: str
    title: str
    reason: str
    status: str
    detail: str
    payload: dict[str, Any]
    runnable: bool
    next_step: str


def build_approval_run_plans(workspace: Path, *, request_id: str | None = None) -> list[ApprovalRunPlan]:
    """Build review plans for approved requests.

    Only approved requests are returned. Pending, rejected and handled requests
    are intentionally excluded from run plans.
    """

    if request_id:
        requests = [get_approval_request(workspace, request_id)]
    else:
        requests = list_approval_requests(workspace, status="approved")
    plans: list[ApprovalRunPlan] = []
    for request in requests:
        if request.status != "approved":
            continue
        plans.append(plan_from_request(request))
    return plans


def plan_from_request(request: ApprovalRequest) -> ApprovalRunPlan:
    detail = request.command or request.path or json.dumps(request.payload or {}, sort_keys=True)
    return ApprovalRunPlan(
        id=request.id,
        action_type=request.action_type,
        title=request.title,
        reason=request.reason,
        status=request.status,
        detail=detail,
        payload=request.payload or {},
        runnable=False,
        next_step="Review the approved item and handle it outside cagent, then mark it handled.",
    )


def mark_approval_handled(workspace: Path, request_id: str, *, note: str = "Handled after review.") -> ApprovalRequest:
    request = get_approval_request(workspace, request_id)
    if request.status != "approved":
        raise ValueError(f"approval request must be approved before it can be marked handled: {request.status}")
    return update_approval_status(workspace, request_id, status="handled", response_note=note)


def format_run_plans(plans: list[ApprovalRunPlan]) -> str:
    if not plans:
        return "No approved approval requests are ready for handling."
    lines: list[str] = ["Approved approval request plan(s):"]
    for plan in plans:
        lines.append(f"- {plan.id} [{plan.action_type}] {plan.title}")
        lines.append(f"  reason: {plan.reason}")
        if plan.detail:
            lines.append(f"  detail: {plan.detail}")
        lines.append(f"  runnable: {plan.runnable}")
        lines.append(f"  next: {plan.next_step}")
    return "\n".join(lines)


def run_plans_json(plans: list[ApprovalRunPlan]) -> str:
    return json.dumps([asdict(item) for item in plans], indent=2, sort_keys=True) + "\n"
