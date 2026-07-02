import json
from http import HTTPStatus
from urllib.parse import urlencode

from cagent.project_engine import create_project
from cagent.web_ui import CagentWebHandler, render_dashboard, status_payload


def test_status_payload_includes_project_and_security(tmp_path):
    create_project(
        root=tmp_path,
        name="Demo UI",
        project_type="software_project",
        goal="Show state.",
        init_git=False,
        create_hooks=False,
    )
    (tmp_path / ".env").write_text("TOKEN=1234567890abcdef\n", encoding="utf-8")

    payload = status_payload(tmp_path)

    assert payload["project"]["name"] == "Demo UI"
    assert "T001" in payload["next_action"]
    assert payload["secret_findings"]
    assert "trust" in payload["trust_status"].lower()


def test_render_dashboard_contains_main_sections(tmp_path):
    create_project(
        root=tmp_path,
        name="Demo UI",
        project_type="software_project",
        goal="Show state.",
        init_git=False,
        create_hooks=False,
    )

    html = render_dashboard(tmp_path)

    assert "Project" in html
    assert "Tasks" in html
    assert "Security" in html
    assert "Run logs" in html


def test_handler_get_status_returns_json(tmp_path):
    create_project(
        root=tmp_path,
        name="Demo UI",
        project_type="software_project",
        goal="Show state.",
        init_git=False,
        create_hooks=False,
    )
    handler = _make_handler(tmp_path)

    handler.do_GET()

    assert handler.status == HTTPStatus.OK.value
    payload = json.loads(handler.body.decode("utf-8"))
    assert payload["project"]["name"] == "Demo UI"


def test_handler_post_trust_redirects_and_writes_status(tmp_path):
    create_project(
        root=tmp_path,
        name="Demo UI",
        project_type="software_project",
        goal="Show state.",
        init_git=False,
        create_hooks=False,
    )
    body = urlencode({"reason": "Trusted in test"}).encode("utf-8")
    handler = _make_handler(tmp_path, path="/actions/trust", method="POST", body=body)

    handler.do_POST()

    assert handler.status == HTTPStatus.SEE_OTHER.value
    assert (tmp_path / ".cagent" / "trust.json").exists()


def _make_handler(tmp_path, *, path="/api/status", method="GET", body=b""):
    class TestHandler(CagentWebHandler):
        workspace = tmp_path

        def __init__(self):
            self.path = path
            self.command = method
            self.headers = {"Content-Length": str(len(body))}
            self.rfile = _Reader(body)
            self.wfile = _Writer()
            self.status = None
            self.body = b""

        def send_response(self, code, message=None):
            self.status = code

        def send_header(self, keyword, value):
            return None

        def end_headers(self):
            return None

    handler = TestHandler()
    handler.wfile.handler = handler
    return handler


class _Reader:
    def __init__(self, body):
        self.body = body

    def read(self, length):
        return self.body[:length]


class _Writer:
    def __init__(self):
        self.handler = None

    def write(self, data):
        self.handler.body += data
        return len(data)
