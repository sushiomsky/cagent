import json

from cagent.project_engine import (
    ToolItem,
    add_research_note,
    add_tool,
    create_project,
    load_project,
    load_tasks,
    next_action,
    project_paths,
    update_task_status,
    verify_project,
    write_final_report,
)


def test_create_project_writes_core_files(tmp_path):
    create_project(
        root=tmp_path,
        name="Demo Agent",
        project_type="llm_agent",
        goal="Build a useful local agent.",
        init_git=False,
        create_hooks=False,
    )

    assert (tmp_path / "PROJECT_SPEC.md").exists()
    assert (tmp_path / "TASKS.md").exists()
    assert (tmp_path / "WORKFLOW.md").exists()
    assert (tmp_path / "AGENTS.md").exists()
    assert (tmp_path / ".cagent" / "project.json").exists()
    assert (tmp_path / ".cagent" / "tasks.json").exists()
    assert (tmp_path / ".cagent" / "tools.json").exists()

    spec = load_project(tmp_path)
    assert spec.name == "Demo Agent"
    assert spec.project_type == "llm_agent"
    assert spec.allowed_actions["research"] is True


def test_next_action_returns_first_open_task(tmp_path):
    create_project(
        root=tmp_path,
        name="Demo",
        project_type="software_project",
        goal="Build it.",
        init_git=False,
        create_hooks=False,
    )

    assert "T001" in next_action(tmp_path)


def test_update_task_status_persists_json_and_markdown(tmp_path):
    create_project(
        root=tmp_path,
        name="Demo",
        project_type="software_project",
        goal="Build it.",
        init_git=False,
        create_hooks=False,
    )

    updated = update_task_status(tmp_path, "T001", "verified", "Looks good")

    assert updated.status == "verified"
    tasks = load_tasks(tmp_path)
    assert tasks[0].status == "verified"
    assert "T001" in (tmp_path / "TASKS.md").read_text(encoding="utf-8")


def test_add_tool_registers_or_replaces_tool(tmp_path):
    create_project(
        root=tmp_path,
        name="Demo",
        project_type="software_project",
        goal="Build it.",
        init_git=False,
        create_hooks=False,
    )

    add_tool(tmp_path, ToolItem(name="custom", purpose="Do custom work"))
    add_tool(tmp_path, ToolItem(name="custom", purpose="Updated purpose", status="available"))

    data = json.loads((tmp_path / ".cagent" / "tools.json").read_text(encoding="utf-8"))
    matches = [item for item in data["tools"] if item["name"] == "custom"]
    assert len(matches) == 1
    assert matches[0]["purpose"] == "Updated purpose"
    assert matches[0]["status"] == "available"


def test_add_research_note_writes_markdown_and_decision_log(tmp_path):
    create_project(
        root=tmp_path,
        name="Demo",
        project_type="research_report",
        goal="Research it.",
        init_git=False,
        create_hooks=False,
    )

    note = add_research_note(
        tmp_path,
        topic="Local models",
        source="manual",
        summary="14B model is default.",
        decision="Use 14B.",
    )

    assert note.exists()
    assert "14B model" in note.read_text(encoding="utf-8")
    assert project_paths(tmp_path).decisions_jsonl.exists()


def test_verify_project_reports_open_tasks_until_done(tmp_path):
    create_project(
        root=tmp_path,
        name="Demo",
        project_type="software_project",
        goal="Build it.",
        init_git=False,
        create_hooks=False,
    )

    result = verify_project(tmp_path)
    assert not result.ok
    assert any("open tasks" in item for item in result.warnings)

    for task in load_tasks(tmp_path):
        update_task_status(tmp_path, task.id, "verified")

    result = verify_project(tmp_path)
    assert result.ok


def test_write_final_report_creates_report(tmp_path):
    create_project(
        root=tmp_path,
        name="Demo",
        project_type="software_project",
        goal="Build it.",
        init_git=False,
        create_hooks=False,
    )

    path = write_final_report(tmp_path, notes="Finished enough for review.")

    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "Final Report" in text
    assert "Finished enough" in text
