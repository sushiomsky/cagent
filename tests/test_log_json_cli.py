import json

from cagent.log_json_cli import main


def write_log(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    events = [
        {
            "time": "2026-01-01T00:00:00Z",
            "event": "start",
            "payload": {"run_id": "run-1", "goal": "demo", "model": "m", "model_role": "fast"},
        },
        {"time": "2026-01-01T00:00:01Z", "event": "finish", "payload": {"message": "done"}},
    ]
    path.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")


def test_logs_json_cli_prints_empty_list_for_no_logs(tmp_path, capsys):
    code = main(["--workspace", str(tmp_path)])
    output = capsys.readouterr().out

    assert code == 0
    assert json.loads(output) == []


def test_logs_json_cli_prints_summaries(tmp_path, capsys):
    write_log(tmp_path / ".cagent-runs" / "run.jsonl")

    code = main(["--workspace", str(tmp_path)])
    output = capsys.readouterr().out

    assert code == 0
    payload = json.loads(output)
    assert payload[0]["run_id"] == "run-1"
    assert payload[0]["goal"] == "demo"


def test_logs_json_cli_prints_latest_events(tmp_path, capsys):
    write_log(tmp_path / ".cagent-runs" / "run.jsonl")

    code = main(["--workspace", str(tmp_path), "--latest", "--max-events", "1"])
    output = capsys.readouterr().out

    assert code == 0
    payload = json.loads(output)
    assert len(payload) == 1
    assert payload[0]["event"] == "finish"
