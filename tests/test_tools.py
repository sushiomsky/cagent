import subprocess
from pathlib import Path

from cagent.tools import WorkspaceTools


def make_tools(
    tmp_path: Path,
    *,
    write: bool = True,
    shell: bool = False,
    dry_run: bool = False,
    command_profile: str = "inspect",
    auto_approve_shell: bool = False,
) -> WorkspaceTools:
    return WorkspaceTools(
        workspace=tmp_path,
        allow_write=write,
        allow_shell=shell,
        dry_run=dry_run,
        shell_timeout_seconds=5,
        command_profile=command_profile,
        auto_approve_shell=auto_approve_shell,
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


def test_repo_map_tool_returns_symbols(tmp_path):
    tools = make_tools(tmp_path)
    (tmp_path / "agent.py").write_text("class CodingAgent:\n    pass\n", encoding="utf-8")

    result = tools.repo_map(query="CodingAgent")

    assert result.ok
    assert "agent.py" in result.output
    assert "CodingAgent" in result.output


def test_context_pack_tool_returns_file_content(tmp_path):
    tools = make_tools(tmp_path)
    (tmp_path / "agent.py").write_text("class CodingAgent:\n    pass\n", encoding="utf-8")

    result = tools.context_pack(query="CodingAgent", max_files=1, max_chars=1000)

    assert result.ok
    assert "--- FILE: agent.py" in result.output
    assert "class CodingAgent" in result.output


def test_apply_patch_changes_existing_file(tmp_path):
    tools = make_tools(tmp_path, write=True)
    (tmp_path / "a.txt").write_text("alpha\nbeta\n", encoding="utf-8")

    result = tools.apply_patch(
        patch="""--- a/a.txt
+++ b/a.txt
@@ -1,2 +1,2 @@
 alpha
-beta
+gamma
"""
    )

    assert result.ok
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "alpha\ngamma\n"


def test_apply_patch_check_only_does_not_write(tmp_path):
    tools = make_tools(tmp_path, write=True)
    (tmp_path / "a.txt").write_text("alpha\nbeta\n", encoding="utf-8")

    result = tools.apply_patch(
        patch="""--- a/a.txt
+++ b/a.txt
@@ -1,2 +1,2 @@
 alpha
-beta
+gamma
""",
        check_only=True,
    )

    assert result.ok
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "alpha\nbeta\n"


def test_apply_patch_requires_write_when_not_check_only(tmp_path):
    tools = make_tools(tmp_path, write=False)

    result = tools.apply_patch(patch="--- a/a.txt\n+++ b/a.txt\n")

    assert not result.ok
    assert "disabled" in result.output


def test_shell_disabled_by_default(tmp_path):
    tools = make_tools(tmp_path, shell=False)

    result = tools.run_shell(command="echo hello")
    assert not result.ok
    assert "Shell access is disabled" in result.output


def test_shell_blocks_policy_denied_command(tmp_path):
    tools = make_tools(tmp_path, shell=True, command_profile="inspect")

    result = tools.run_shell(command="pytest -q")
    assert not result.ok
    assert "Blocked by command profile" in result.output


def test_shell_requires_approval_for_write_command(tmp_path):
    tools = make_tools(tmp_path, shell=True, command_profile="edit")

    result = tools.run_shell(command="touch generated.txt")
    assert not result.ok
    assert "requires approval" in result.output


def test_shell_auto_approve_runs_policy_allowed_command(tmp_path):
    tools = make_tools(
        tmp_path,
        shell=True,
        command_profile="edit",
        auto_approve_shell=True,
    )

    result = tools.run_shell(command="touch generated.txt")
    assert result.ok
    assert (tmp_path / "generated.txt").exists()


def test_search_text(tmp_path):
    tools = make_tools(tmp_path)
    tools.write_file(path="a.txt", content="alpha\nbeta\n")

    result = tools.search_text(pattern="beta")
    assert result.ok
    assert "a.txt:2: beta" in result.output


def test_git_diff_reports_status(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    tools = make_tools(tmp_path)
    (tmp_path / "a.txt").write_text("alpha\n", encoding="utf-8")

    result = tools.git_diff()

    assert result.ok
    assert "?? a.txt" in result.output


def test_discover_tests_for_python_project(tmp_path):
    tools = make_tools(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")

    result = tools.discover_tests()

    assert result.ok
    assert "pytest -q" in result.output
