"""Dependency-free local web UI for cagent project state."""

from __future__ import annotations

import html
import json
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from cagent.approval_queue import list_approval_requests, update_approval_status
from cagent.log_viewer import format_events, list_run_logs, summarize_run_log
from cagent.project_engine import load_project, load_tasks, next_action, verify_project, write_final_report
from cagent.secret_scan import scan_workspace
from cagent.trust import format_trust_status, trust_workspace

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def serve_web_ui(*, workspace: Path, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> int:
    """Serve the local web UI until interrupted."""

    root = workspace.resolve()

    class Handler(CagentWebHandler):
        workspace = root

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"cagent web UI: http://{host}:{port}/?workspace={root}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 130
    finally:
        server.server_close()
    return 0


class CagentWebHandler(BaseHTTPRequestHandler):
    """Small HTML/JSON handler for local-only project observability."""

    workspace: Path = Path(".").resolve()

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API.
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(render_dashboard(self.workspace))
            return
        if parsed.path == "/api/status":
            self._send_json(status_payload(self.workspace))
            return
        if parsed.path == "/logs":
            query = parse_qs(parsed.query)
            selected = query.get("file", [""])[0]
            self._send_html(render_logs(self.workspace, selected=selected))
            return
        self._send_text("not found", status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API.
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length).decode("utf-8") if length else ""
        data = parse_qs(body)

        if parsed.path == "/actions/trust":
            reason = data.get("reason", ["Trusted from cagent web UI."])[0]
            trust_workspace(self.workspace, reason=reason)
            self._redirect("/")
            return
        if parsed.path == "/actions/final-report":
            notes = data.get("notes", ["Generated from cagent web UI."])[0]
            write_final_report(self.workspace, notes=notes)
            self._redirect("/")
            return
        if parsed.path == "/actions/approval":
            request_id = data.get("id", [""])[0]
            action = data.get("action", [""])[0]
            note = data.get("note", ["Reviewed from cagent web UI."])[0]
            if action not in {"approved", "rejected"}:
                self._send_text("invalid approval action", status=HTTPStatus.BAD_REQUEST)
                return
            update_approval_status(self.workspace, request_id, status=action, response_note=note)
            self._redirect("/")
            return
        self._send_text("not found", status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature.
        return

    def _send_html(self, text: str, *, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status.value)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(text.encode("utf-8"))

    def _send_json(self, payload: dict[str, Any], *, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(json.dumps(payload, indent=2, sort_keys=True, default=str).encode("utf-8"))

    def _send_text(self, text: str, *, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status.value)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(text.encode("utf-8"))

    def _redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER.value)
        self.send_header("Location", location)
        self.end_headers()


def status_payload(workspace: Path) -> dict[str, Any]:
    root = workspace.resolve()
    payload: dict[str, Any] = {"workspace": str(root)}
    try:
        spec = load_project(root)
        tasks = load_tasks(root)
        verification = verify_project(root)
        payload.update(
            {
                "project": asdict(spec),
                "tasks": [asdict(task) for task in tasks],
                "next_action": next_action(root),
                "verification": asdict(verification),
            }
        )
    except Exception as exc:  # noqa: BLE001 - UI must stay available for broken workspaces.
        payload["project_error"] = f"{type(exc).__name__}: {exc}"
    findings = scan_workspace(root, max_files=300)
    payload["secret_findings"] = [asdict(item) for item in findings]
    payload["trust_status"] = format_trust_status(root)
    payload["logs"] = [asdict(summarize_run_log(path)) for path in list_run_logs(root)[:20]]
    payload["approvals"] = [asdict(item) for item in list_approval_requests(root, status="all")]
    return payload


def render_dashboard(workspace: Path) -> str:
    root = workspace.resolve()
    payload = status_payload(root)
    project = payload.get("project") or {}
    tasks = payload.get("tasks") or []
    verification = payload.get("verification") or {}
    findings = payload.get("secret_findings") or []
    logs = payload.get("logs") or []
    approvals = payload.get("approvals") or []
    pending_approvals = [item for item in approvals if item.get("status") == "pending"]

    return page(
        "cagent dashboard",
        f"""
        <section class="card">
          <h2>Project</h2>
          <p><strong>Workspace:</strong> <code>{e(root)}</code></p>
          <p><strong>Name:</strong> {e(project.get('name', 'No project initialized'))}</p>
          <p><strong>Type:</strong> <code>{e(project.get('project_type', 'unknown'))}</code></p>
          <p><strong>Goal:</strong> {e(project.get('goal', payload.get('project_error', '')))}</p>
          <p><strong>Next:</strong> {e(payload.get('next_action', 'Run cagent init-project first.'))}</p>
        </section>

        <section class="card grid2">
          <div>
            <h2>Verification</h2>
            <p class="badge {'ok' if verification.get('ok') else 'warn'}">{'PASS' if verification.get('ok') else 'NEEDS WORK'}</p>
            <h3>Warnings</h3>
            {render_list(verification.get('warnings', []), empty='No warnings.')}
            <h3>Missing</h3>
            {render_list(verification.get('missing', []), empty='Nothing missing.')}
          </div>
          <div>
            <h2>Security</h2>
            <pre>{e(payload.get('trust_status', ''))}</pre>
            <p class="badge {'ok' if not findings else 'warn'}">{len(findings)} likely secret finding(s)</p>
            {render_findings(findings)}
          </div>
        </section>

        <section class="card">
          <h2>Approval review</h2>
          <p class="badge {'ok' if not pending_approvals else 'warn'}">{len(pending_approvals)} pending approval(s)</p>
          {render_approvals(approvals)}
        </section>

        <section class="card">
          <h2>Tasks</h2>
          {render_tasks(tasks)}
        </section>

        <section class="card grid2">
          <div>
            <h2>Actions</h2>
            <form method="post" action="/actions/trust">
              <label>Trust reason</label>
              <input name="reason" value="Reviewed from cagent web UI." />
              <button type="submit">Trust workspace</button>
            </form>
            <form method="post" action="/actions/final-report">
              <label>Final report notes</label>
              <input name="notes" value="Generated from cagent web UI." />
              <button type="submit">Generate final report</button>
            </form>
          </div>
          <div>
            <h2>Run logs</h2>
            {render_logs_list(logs)}
          </div>
        </section>
        """,
    )


def render_logs(workspace: Path, *, selected: str) -> str:
    root = workspace.resolve()
    logs = list_run_logs(root)
    if selected:
        selected_path = root / ".cagent-runs" / selected
    else:
        selected_path = logs[0] if logs else None
    content = "No run logs found."
    if selected_path and selected_path.exists():
        content = format_events(selected_path, max_events=80)
    return page(
        "cagent logs",
        f"""
        <section class="card">
          <p><a href="/">Back to dashboard</a></p>
          <h2>Logs</h2>
          {render_logs_list([asdict(summarize_run_log(path)) for path in logs[:20]])}
          <pre>{e(content)}</pre>
        </section>
        """,
    )


def render_tasks(tasks: list[dict[str, Any]]) -> str:
    if not tasks:
        return "<p>No tasks found.</p>"
    rows = "".join(
        f"<tr><td><code>{e(item.get('id', ''))}</code></td><td>{e(item.get('status', ''))}</td><td>{e(item.get('owner', ''))}</td><td>{e(item.get('title', ''))}</td></tr>"
        for item in tasks
    )
    return f"<table><thead><tr><th>ID</th><th>Status</th><th>Owner</th><th>Title</th></tr></thead><tbody>{rows}</tbody></table>"


def render_approvals(approvals: list[dict[str, Any]]) -> str:
    if not approvals:
        return "<p>No approval requests found.</p>"
    rows = []
    for item in approvals:
        controls = ""
        if item.get("status") == "pending":
            controls = (
                f"<form method='post' action='/actions/approval' class='inline'>"
                f"<input type='hidden' name='id' value='{e(item.get('id', ''))}' />"
                f"<input type='hidden' name='action' value='approved' />"
                f"<input type='hidden' name='note' value='Approved from cagent web UI.' />"
                f"<button type='submit'>Approve</button>"
                f"</form> "
                f"<form method='post' action='/actions/approval' class='inline'>"
                f"<input type='hidden' name='id' value='{e(item.get('id', ''))}' />"
                f"<input type='hidden' name='action' value='rejected' />"
                f"<input type='hidden' name='note' value='Rejected from cagent web UI.' />"
                f"<button type='submit'>Reject</button>"
                f"</form>"
            )
        rows.append(
            "<tr>"
            f"<td><code>{e(item.get('id', ''))}</code></td>"
            f"<td>{e(item.get('status', ''))}</td>"
            f"<td>{e(item.get('action_type', ''))}</td>"
            f"<td>{e(item.get('title', ''))}<br><small>{e(item.get('reason', ''))}</small></td>"
            f"<td><code>{e(item.get('command', item.get('path', '')))}</code></td>"
            f"<td>{controls}</td>"
            "</tr>"
        )
    return "<table><thead><tr><th>ID</th><th>Status</th><th>Type</th><th>Request</th><th>Detail</th><th>Review</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def render_findings(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return "<p>No likely secrets found.</p>"
    return "<ul>" + "".join(
        f"<li><code>{e(item.get('path', ''))}:{e(item.get('line', ''))}</code> {e(item.get('kind', ''))} — {e(item.get('preview', ''))}</li>"
        for item in findings[:20]
    ) + "</ul>"


def render_logs_list(logs: list[dict[str, Any]]) -> str:
    if not logs:
        return "<p>No run logs found.</p>"
    return "<ul>" + "".join(
        f"<li><a href='/logs?file={e(Path(str(item.get('path', ''))).name)}'>{e(Path(str(item.get('path', ''))).name)}</a> — {e(item.get('events', '0'))} events — {e(item.get('goal', ''))}</li>"
        for item in logs
    ) + "</ul>"


def render_list(items: list[Any], *, empty: str) -> str:
    if not items:
        return f"<p>{e(empty)}</p>"
    return "<ul>" + "".join(f"<li>{e(item)}</li>" for item in items) + "</ul>"


def page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{e(title)}</title>
<style>
body{{font-family:system-ui,sans-serif;margin:0;background:#f6f8fa;color:#17202a}}
header{{background:#111827;color:white;padding:1rem 2rem}}
main{{max-width:1180px;margin:1rem auto;padding:0 1rem}}
.card{{background:white;border:1px solid #d8dee4;border-radius:10px;padding:1rem;margin:1rem 0;box-shadow:0 1px 2px rgba(0,0,0,.04)}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:1rem}}
table{{width:100%;border-collapse:collapse}}th,td{{border-bottom:1px solid #eee;text-align:left;padding:.5rem;vertical-align:top}}
pre{{background:#f6f8fa;border:1px solid #eee;padding:1rem;overflow:auto}}
.badge{{display:inline-block;padding:.3rem .6rem;border-radius:999px;font-weight:700}}.ok{{background:#dcfce7;color:#166534}}.warn{{background:#fef3c7;color:#92400e}}
input{{display:block;width:100%;padding:.5rem;margin:.25rem 0 .75rem;border:1px solid #ccc;border-radius:6px}}button{{padding:.5rem .75rem;border:0;border-radius:6px;background:#2563eb;color:white;font-weight:700}}a{{color:#2563eb}}
.inline{{display:inline}}.inline input{{display:none}}.inline button{{margin:.1rem}}
small{{color:#57606a}}
@media(max-width:800px){{.grid2{{grid-template-columns:1fr}}}}
</style></head><body><header><h1>{e(title)}</h1></header><main>{body}</main></body></html>"""


def e(value: Any) -> str:
    return html.escape(str(value), quote=True)
