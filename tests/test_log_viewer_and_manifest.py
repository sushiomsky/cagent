import json

from cagent.log_viewer import format_events, list_run_logs, render_html, summarize_run_log
from cagent.mcp_manifest import build_manifest, manifest_json


def test_log_viewer_summarizes_run_log(tmp_path):
    log_dir = tmp_path / ".cagent-runs"
    log_dir.mkdir()
    log = log_dir / "20260101T000000Z-demo.jsonl"
    log.write_text(
        json.dumps(
            {
                "event": "run_start",
                "time": "2026-01-01T00:00:00Z",
                "payload": {
                    "run_id": "abc",
                    "goal": "Do work",
                    "model": "model-a",
                    "model_role": "default",
                },
            }
        )
        + "\n"
        + json.dumps(
            {
                "event": "finish",
                "time": "2026-01-01T00:00:01Z",
                "payload": {"message": "done"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    logs = list_run_logs(tmp_path)
    assert logs == [log]

    summary = summarize_run_log(log)
    assert summary.goal == "Do work"
    assert summary.finished is True
    assert summary.events == 2

    assert "finish" in format_events(log)
    assert "<html" in render_html(log)


def test_mcp_manifest_is_stable_json():
    manifest = build_manifest()

    assert manifest["name"] == "cagent"
    assert any(item["name"] == "init-project" for item in manifest["capabilities"])
    assert json.loads(manifest_json())["name"] == "cagent"
