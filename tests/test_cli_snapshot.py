from cagent.cli import main
from cagent.project_snapshot import save_snapshot


def test_snapshot_command_prints_current_snapshot(tmp_path, capsys):
    save_snapshot(tmp_path, action="T001", result="done", steps=2)

    code = main(["snapshot", "--workspace", str(tmp_path)])
    output = capsys.readouterr().out

    assert code == 0
    assert "count: 1" in output
    assert "action: T001" in output
    assert "result: done" in output
