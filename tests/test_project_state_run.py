from cagent.project_state_run import (
    format_project_run_state,
    load_project_run_state,
    project_run_state_path,
    record_project_run_state,
)


def test_load_project_run_state_defaults(tmp_path):
    state = load_project_run_state(tmp_path)

    assert state.run_count == 0
    assert state.current_action == ""
    assert state.updated_at


def test_record_project_run_state_persists_and_increments(tmp_path):
    first = record_project_run_state(
        tmp_path,
        current_action="T001",
        last_result="first result",
        last_step_count=2,
        last_run_log="run1.jsonl",
    )
    second = record_project_run_state(
        tmp_path,
        current_action="T002",
        last_result="second result",
        last_step_count=3,
    )

    assert project_run_state_path(tmp_path).exists()
    assert first.run_count == 1
    assert second.run_count == 2
    assert second.current_action == "T002"
    assert second.last_step_count == 3
    assert load_project_run_state(tmp_path) == second


def test_format_project_run_state_is_human_readable(tmp_path):
    state = record_project_run_state(
        tmp_path,
        current_action="T001",
        last_result="done",
        last_step_count=1,
    )

    output = format_project_run_state(state)

    assert "runs: 1" in output
    assert "current_action: T001" in output
    assert "last_result: done" in output
