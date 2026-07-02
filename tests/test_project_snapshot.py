from cagent.project_snapshot import format_snapshot, load_snapshot, save_snapshot, snapshot_path


def test_load_snapshot_defaults(tmp_path):
    snapshot = load_snapshot(tmp_path)

    assert snapshot.count == 0
    assert snapshot.action == ""
    assert snapshot.updated_at


def test_save_snapshot_persists_and_increments(tmp_path):
    first = save_snapshot(tmp_path, action="T001", result="first", steps=2, log_path="a.jsonl")
    second = save_snapshot(tmp_path, action="T002", result="second", steps=3)

    assert snapshot_path(tmp_path).exists()
    assert first.count == 1
    assert second.count == 2
    assert second.action == "T002"
    assert second.steps == 3
    assert load_snapshot(tmp_path) == second


def test_format_snapshot_is_human_readable(tmp_path):
    snapshot = save_snapshot(tmp_path, action="T001", result="done", steps=1)

    output = format_snapshot(snapshot)

    assert "count: 1" in output
    assert "action: T001" in output
    assert "result: done" in output
