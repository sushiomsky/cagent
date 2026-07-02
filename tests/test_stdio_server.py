import json
from io import StringIO

from cagent.project_engine import create_project
from cagent.project_snapshot import save_snapshot
from cagent.stdio_server import handle_json_line, serve_stdio


def rpc(method, params=None, request_id=1):
    payload = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        payload["params"] = params
    return json.dumps(payload)


def test_initialize_response_contains_server_info():
    response = handle_json_line(rpc("initialize"))

    assert response["result"]["serverInfo"]["name"] == "cagent-stdio"
    assert response["result"]["capabilities"]["tools"]
    assert response["result"]["capabilities"]["resources"]


def test_tools_list_includes_project_tools():
    response = handle_json_line(rpc("tools/list"))

    tools = response["result"]["tools"]
    assert any(tool["name"] == "cagent.resume" for tool in tools)
    assert any(tool["name"] == "cagent.secret_scan" for tool in tools)


def test_resources_list_includes_project_resources(tmp_path):
    create_project(
        root=tmp_path,
        name="Demo",
        project_type="software_project",
        goal="Build it.",
        init_git=False,
        create_hooks=False,
    )
    save_snapshot(tmp_path, action="T001", result="done", steps=1)

    response = handle_json_line(rpc("resources/list", {"workspace": str(tmp_path)}))

    resources = response["result"]["resources"]
    uris = {item["uri"] for item in resources}
    assert "cagent://project/spec" in uris
    assert "cagent://project/tasks" in uris
    assert "cagent://project/snapshot" in uris
    assert any(item["exists"] for item in resources if item["uri"] == "cagent://project/snapshot")


def test_resources_read_returns_text(tmp_path):
    create_project(
        root=tmp_path,
        name="Demo",
        project_type="software_project",
        goal="Build it.",
        init_git=False,
        create_hooks=False,
    )

    response = handle_json_line(
        rpc(
            "resources/read",
            {"workspace": str(tmp_path), "uri": "cagent://project/spec"},
        )
    )

    contents = response["result"]["contents"]
    assert contents[0]["uri"] == "cagent://project/spec"
    assert "Project Spec: Demo" in contents[0]["text"]


def test_resources_read_unknown_uri_returns_error(tmp_path):
    response = handle_json_line(
        rpc(
            "resources/read",
            {"workspace": str(tmp_path), "uri": "cagent://project/missing"},
        )
    )

    assert response["error"]["code"] == -32602


def test_tools_call_resume_reads_project_state(tmp_path):
    create_project(
        root=tmp_path,
        name="Demo",
        project_type="software_project",
        goal="Build it.",
        init_git=False,
        create_hooks=False,
    )

    response = handle_json_line(
        rpc(
            "tools/call",
            {
                "name": "cagent.resume",
                "arguments": {"workspace": str(tmp_path)},
            },
        )
    )

    content = response["result"]["content"]
    assert content[0]["type"] == "text"
    assert "T001" in content[0]["text"]


def test_tools_call_secret_scan_reports_findings(tmp_path):
    (tmp_path / ".env").write_text("API_KEY=1234567890abcdef\n", encoding="utf-8")

    response = handle_json_line(
        rpc(
            "tools/call",
            {
                "name": "cagent.secret_scan",
                "arguments": {"workspace": str(tmp_path)},
            },
        )
    )

    text = response["result"]["content"][0]["text"]
    assert "Likely secrets" in text
    assert "<REDACTED" in text


def test_unknown_method_returns_json_rpc_error():
    response = handle_json_line(rpc("missing/method"))

    assert response["error"]["code"] == -32601


def test_serve_stdio_handles_shutdown():
    stdin = StringIO(rpc("shutdown") + "\n")
    stdout = StringIO()

    exit_code = serve_stdio(stdin=stdin, stdout=stdout)

    assert exit_code == 0
    response = json.loads(stdout.getvalue())
    assert response["result"] == {"shutdown": True}
