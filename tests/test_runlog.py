import json

from cagent.runlog import RunLogger


def test_run_logger_writes_jsonl_events(tmp_path):
    logger = RunLogger(
        workspace=tmp_path,
        goal="do the thing",
        model="test-model",
        model_role="reviewer",
        base_url="http://127.0.0.1:18080/v1",
    )
    logger.record("custom", {"value": 123})

    lines = logger.path.read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in lines]

    assert logger.path.parent.name == ".cagent-runs"
    assert events[0]["event"] == "run_start"
    assert events[0]["payload"]["goal"] == "do the thing"
    assert events[0]["payload"]["model"] == "test-model"
    assert events[0]["payload"]["model_role"] == "reviewer"
    assert events[1]["event"] == "custom"
    assert events[1]["payload"] == {"value": 123}
