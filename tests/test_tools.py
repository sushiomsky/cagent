from pathlib import Path

from cagent.tools import WorkspaceTools


def make_tools(tmp_path: Path, *, write: bool = True, shell: bool = False) -> WorkspaceTools:
    return WorkspaceTools(
        workspace=tmp_path,
        allow_write=write,
        allow_shell=shell,
        dry_run=False,
        shell_timeout_seconds=5,
    )


def test_write_and_read_file_inside_workspace(tmp_path):
    tools = make_tools(tmp_path)

    write_result = tools.write_file(path="src/example.txt", content="hello\nworld\n")
    assert write_result.ok

    read_result = tools.read_file(path="src/example.txt")
    assert read_result.ok
    assert "1: hello" in read_result.output
    assert "2: world" in read_result.output


def test_rejects_workspace_escape(tmp_path):
    tools = make_tools(tmp_path)

    result = tools.write_file(path="../escape.txt", content="nope")
    assert not result.ok
    assert "escapes workspace" in result.output


def test_shell_disabled_by_default(tmp_path):
    tools = make_tools(tmp_path, shell=False)

    result = tools.run_shell(command="echo hello")
    assert not result.ok
    assert "Shell access is disabled" in result.output


def test_shell_blocks_dangerous_command(tmp_path):
    tools = make_tools(tmp_path, shell=True)

    result = tools.run_shell(command="rm -rf /")
    assert not result.ok
    assert "Blocked dangerous command" in result.output


def test_search_text(tmp_path):
    tools = make_tools(tmp_path)
    tools.write_file(path="a.txt", content="alpha\nbeta\n")

    result = tools.search_text(pattern="beta")
    assert result.ok
    assert "a.txt:2: beta" in result.output
