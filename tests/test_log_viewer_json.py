import json

from cagent.log_viewer import events_json, summaries_json, summarize_run_log, summary_to_dict


def write_log(path):
    events = [
        {
            "time": "2026-01-01T00:00:00Z",
            "event": "start",
            "payload": {
                "run_id": "run-1",
                "goal": "demo goal",
                "model": "demo-model",
                "model_role": "fast",
            },
        },
        {
            "time": "2026-01-01T00:00:01Z",
            "event": "finish",
            "payload": {"message": "done"},
        },
    ]
    path.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")


def test_summary_to_dict_uses_json_safe_path(tmp_path):
    log = tmp_path / "run.jsonl"
    write_log(log)

    payload = summary_to_dict(summarize_run_log(log))

    assert payload["path"] == str(log)
    assert payload["name"] == "run.jsonl"
    assert payload["run_id"] == "run-1"
    assert payload["finished"] is True


def test_summaries_json_returns_json_text(tmp_path):
    log = tmp_path / "run.jsonl"
    write_log(log)

    payload = json.loads(summaries_json([log]))

    assert payload[0]["goal"] == "demo goal"
    assert payload[0]["model_role"] == "fast"


def test_events_json_respects_max_events(tmp_path):
    log = tmp_path / "run.jsonl"
    write_log(log)

    payload = json.loads(events_json(log, max_events=1))

    assert len(payload) == 1
    assert payload[0]["event"] == "finish"
