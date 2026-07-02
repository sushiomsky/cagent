"""Project engine primitives for cagent.

The project engine turns an open-ended request into a persistent project folder
with a spec, task board, workflow, tool registry, artifacts and verification
state. It is intentionally dependency-free so it works in fresh repos.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

ProjectType = Literal[
    "software_project",
    "research_report",
    "automation_script",
    "data_analysis",
    "web_app",
    "cli_tool",
    "telegram_bot",
    "browser_automation",
    "llm_agent",
    "documentation_project",
    "simulation_project",
    "general_task",
]
TaskStatus = Literal["todo", "in_progress", "blocked", "needs_user", "done", "verified"]
ArtifactStatus = Literal["planned", "draft", "final"]

DEFAULT_PROJECT_TYPE: ProjectType = "software_project"
PROJECT_TYPES: tuple[ProjectType, ...] = (
    "software_project",
    "research_report",
    "automation_script",
    "data_analysis",
    "web_app",
    "cli_tool",
    "telegram_bot",
    "browser_automation",
    "llm_agent",
    "documentation_project",
    "simulation_project",
    "general_task",
)

DEFAULT_DOD = [
    "Project spec exists and matches the requested goal.",
    "Task board exists and every task is done, verified, blocked, or documented.",
    "Required deliverables are created or explicitly listed as open work.",
    "Relevant checks/tests were run or explicitly marked not applicable.",
    "Final report explains what changed, how it was verified, and what remains.",
]

AGENT_ROLE_TEMPLATES = [
    {
        "name": "planner",
        "model_role": "default",
        "responsibility": "Clarify the goal, split work into tasks, maintain the definition of done.",
    },
    {
        "name": "researcher",
        "model_role": "fast",
        "responsibility": "Collect source notes, compare options, and record decisions.",
    },
    {
        "name": "implementer",
        "model_role": "default",
        "responsibility": "Make project changes, create tools, and keep edits small and reviewable.",
    },
    {
        "name": "tester",
        "model_role": "fast",
        "responsibility": "Discover and run verification checks, then record results.",
    },
    {
        "name": "reviewer",
        "model_role": "reviewer",
        "responsibility": "Review the diff, risks, documentation and final deliverables.",
    },
]

WORKFLOW_STAGES = ["intake", "research", "plan", "bootstrap", "implement", "test", "review", "finalize"]


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class ProjectSpec:
    name: str
    slug: str
    project_type: ProjectType
    goal: str
    deliverables: list[str]
    definition_of_done: list[str]
    constraints: list[str] = field(default_factory=list)
    allowed_actions: dict[str, bool] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)


@dataclass(frozen=True)
class TaskItem:
    id: str
    title: str
    status: TaskStatus = "todo"
    owner: str = "planner"
    verification: str = ""
    notes: str = ""


@dataclass(frozen=True)
class ArtifactItem:
    path: str
    kind: str
    status: ArtifactStatus = "planned"
    created_by: str = "planner"
    description: str = ""


@dataclass(frozen=True)
class ToolItem:
    name: str
    purpose: str
    status: str = "planned"
    install_command: str = ""
    risk: str = "project"
    notes: str = ""


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    checks: list[str]
    missing: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class ProjectPaths:
    root: Path
    cagent_dir: Path
    project_json: Path
    tasks_json: Path
    workflow_json: Path
    tools_json: Path
    artifacts_json: Path
    decisions_jsonl: Path
    research_dir: Path
    final_report: Path


def project_paths(root: Path) -> ProjectPaths:
    cagent_dir = root / ".cagent"
    return ProjectPaths(
        root=root,
        cagent_dir=cagent_dir,
        project_json=cagent_dir / "project.json",
        tasks_json=cagent_dir / "tasks.json",
        workflow_json=cagent_dir / "workflow.json",
        tools_json=cagent_dir / "tools.json",
        artifacts_json=cagent_dir / "artifacts.json",
        decisions_jsonl=cagent_dir / "decisions.jsonl",
        research_dir=root / "docs" / "research",
        final_report=root / "FINAL_REPORT.md",
    )


def create_project(
    *,
    root: Path,
    name: str,
    project_type: str,
    goal: str,
    deliverables: list[str] | None = None,
    definition_of_done: list[str] | None = None,
    constraints: list[str] | None = None,
    allow_research: bool = True,
    allow_write: bool = True,
    allow_shell: bool = False,
    allow_network: bool = False,
    allow_tool_install: bool = False,
    init_git: bool = True,
    create_hooks: bool = True,
) -> ProjectSpec:
    """Create or update the persistent project scaffolding."""

    selected_type = normalize_project_type(project_type)
    spec = ProjectSpec(
        name=name,
        slug=slugify(name),
        project_type=selected_type,
        goal=goal,
        deliverables=deliverables or default_deliverables(selected_type),
        definition_of_done=definition_of_done or DEFAULT_DOD,
        constraints=constraints or [],
        allowed_actions={
            "research": allow_research,
            "write_files": allow_write,
            "shell": allow_shell,
            "network": allow_network,
            "tool_install": allow_tool_install,
        },
    )

    paths = project_paths(root)
    paths.cagent_dir.mkdir(parents=True, exist_ok=True)
    paths.research_dir.mkdir(parents=True, exist_ok=True)
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "tests").mkdir(parents=True, exist_ok=True)

    write_json(paths.project_json, asdict(spec))
    write_json(paths.tasks_json, {"tasks": [asdict(task) for task in default_tasks(spec)]})
    write_json(paths.workflow_json, default_workflow(spec))
    write_json(paths.tools_json, {"tools": [asdict(tool) for tool in default_tools(spec)]})
    write_json(paths.artifacts_json, {"artifacts": [asdict(item) for item in default_artifacts(spec)]})
    append_jsonl(
        paths.decisions_jsonl,
        {
            "time": _now(),
            "type": "project_created",
            "name": spec.name,
            "goal": spec.goal,
            "project_type": spec.project_type,
        },
    )

    write_markdown_files(root, spec)
    ensure_gitignore(root)
    ensure_makefile(root)
    if init_git:
        init_git_repo(root)
    if create_hooks:
        create_git_hooks(root)
    return spec


def normalize_project_type(value: str | None) -> ProjectType:
    normalized = (value or DEFAULT_PROJECT_TYPE).strip().lower().replace("-", "_")
    if normalized not in PROJECT_TYPES:
        valid = ", ".join(PROJECT_TYPES)
        raise ValueError(f"Invalid project type '{value}'. Expected one of: {valid}")
    return normalized  # type: ignore[return-value]


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "cagent-project"


def default_deliverables(project_type: ProjectType) -> list[str]:
    if project_type == "research_report":
        return ["docs/research/report.md", "FINAL_REPORT.md"]
    if project_type == "documentation_project":
        return ["README.md", "docs/", "FINAL_REPORT.md"]
    if project_type in {"automation_script", "simulation_project", "data_analysis"}:
        return ["scripts/", "README.md", "tests/", "FINAL_REPORT.md"]
    return ["README.md", "src/ or scripts/", "tests/", "FINAL_REPORT.md"]


def default_tasks(spec: ProjectSpec) -> list[TaskItem]:
    return [
        TaskItem("T001", "Confirm project goal and definition of done", "todo", "planner"),
        TaskItem("T002", "Collect research notes and constraints", "todo", "researcher"),
        TaskItem("T003", "Create implementation plan and required tool list", "todo", "planner"),
        TaskItem("T004", "Implement the deliverables", "todo", "implementer"),
        TaskItem("T005", "Run verification checks", "todo", "tester"),
        TaskItem("T006", "Review risks, docs and final diff", "todo", "reviewer"),
        TaskItem("T007", "Write final report", "todo", "planner"),
    ]


def default_tools(spec: ProjectSpec) -> list[ToolItem]:
    tools = [
        ToolItem("git", "Version control, diffs and hooks", "required", risk="project"),
        ToolItem("ripgrep", "Fast code and text search", "recommended", "", "project"),
    ]
    if spec.allowed_actions.get("research"):
        tools.append(
            ToolItem("research_notes", "Structured source notes under docs/research/", "available", risk="project")
        )
    if spec.project_type in {"software_project", "cli_tool", "llm_agent", "web_app"}:
        tools.append(ToolItem("pytest", "Python test runner when Python is used", "optional", "pip install pytest", "project"))
    return tools


def default_artifacts(spec: ProjectSpec) -> list[ArtifactItem]:
    artifacts = [
        ArtifactItem("PROJECT_SPEC.md", "project_spec", "final", "planner", "Canonical goal and scope."),
        ArtifactItem("TASKS.md", "task_board", "draft", "planner", "Human-readable task board."),
        ArtifactItem("WORKFLOW.md", "workflow", "draft", "planner", "Agent roles and execution stages."),
        ArtifactItem("AGENTS.md", "agent_roles", "draft", "planner", "Role definitions for cagent and other agents."),
        ArtifactItem("FINAL_REPORT.md", "final_report", "planned", "planner", "Final delivery report."),
    ]
    existing = {item.path for item in artifacts}
    for path in spec.deliverables:
        if path not in existing:
            artifacts.append(ArtifactItem(path, "deliverable", "planned", "planner", "Requested deliverable."))
    return artifacts


def default_workflow(spec: ProjectSpec) -> dict[str, Any]:
    return {
        "project": spec.slug,
        "stages": WORKFLOW_STAGES,
        "agents": AGENT_ROLE_TEMPLATES,
        "loop": {
            "max_iterations": 20,
            "stop_when_definition_of_done_passes": True,
            "require_final_report": True,
            "require_review_before_done": True,
        },
        "policies": spec.allowed_actions,
    }


def write_markdown_files(root: Path, spec: ProjectSpec) -> None:
    (root / "PROJECT_SPEC.md").write_text(render_project_spec(spec), encoding="utf-8")
    (root / "TASKS.md").write_text(render_tasks(default_tasks(spec)), encoding="utf-8")
    (root / "WORKFLOW.md").write_text(render_workflow(default_workflow(spec)), encoding="utf-8")
    (root / "AGENTS.md").write_text(render_agents(), encoding="utf-8")
    readme = root / "README.md"
    if not readme.exists():
        readme.write_text(f"# {spec.name}\n\n{spec.goal}\n", encoding="utf-8")


def render_project_spec(spec: ProjectSpec) -> str:
    return "\n".join(
        [
            f"# Project Spec: {spec.name}",
            "",
            f"Type: `{spec.project_type}`",
            f"Created: {spec.created_at}",
            "",
            "## Goal",
            "",
            spec.goal,
            "",
            "## Deliverables",
            "",
            *[f"- {item}" for item in spec.deliverables],
            "",
            "## Definition of Done",
            "",
            *[f"- [ ] {item}" for item in spec.definition_of_done],
            "",
            "## Constraints",
            "",
            *([f"- {item}" for item in spec.constraints] or ["- None recorded."]),
            "",
            "## Allowed Actions",
            "",
            *[f"- {key}: {value}" for key, value in spec.allowed_actions.items()],
            "",
        ]
    )


def render_tasks(tasks: list[TaskItem]) -> str:
    lines = ["# Tasks", ""]
    for task in tasks:
        lines.append(f"- [ ] **{task.id}** `{task.owner}` {task.title}")
    lines.append("")
    return "\n".join(lines)


def render_workflow(workflow: dict[str, Any]) -> str:
    lines = ["# Workflow", "", "## Stages", ""]
    lines.extend(f"- {stage}" for stage in workflow["stages"])
    lines.extend(["", "## Agents", ""])
    for agent in workflow["agents"]:
        lines.append(f"### {agent['name']}")
        lines.append("")
        lines.append(f"Model role: `{agent['model_role']}`")
        lines.append("")
        lines.append(agent["responsibility"])
        lines.append("")
    return "\n".join(lines)


def render_agents() -> str:
    lines = ["# Agents", ""]
    for agent in AGENT_ROLE_TEMPLATES:
        lines.append(f"## {agent['name']}")
        lines.append("")
        lines.append(f"Model role: `{agent['model_role']}`")
        lines.append("")
        lines.append(agent["responsibility"])
        lines.append("")
    return "\n".join(lines)


def ensure_gitignore(root: Path) -> None:
    path = root / ".gitignore"
    entries = [".venv/", "__pycache__/", ".pytest_cache/", ".mypy_cache/", ".ruff_cache/", ".cagent-runs/"]
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    updated = current
    for entry in entries:
        if entry not in current.splitlines():
            updated += ("\n" if updated and not updated.endswith("\n") else "") + entry + "\n"
    path.write_text(updated, encoding="utf-8")


def ensure_makefile(root: Path) -> None:
    path = root / "Makefile"
    if path.exists():
        return
    path.write_text(
        "check:\n\tpython -m compileall .\n\n"
        "test:\n\tpytest -q\n\n"
        "verify:\n\tcagent verify --workspace .\n",
        encoding="utf-8",
    )


def init_git_repo(root: Path) -> None:
    if (root / ".git").exists():
        return
    subprocess.run(["git", "init"], cwd=root, capture_output=True, text=True, check=False)


def create_git_hooks(root: Path) -> None:
    git_dir = root / ".git"
    if not git_dir.exists():
        return
    hooks = git_dir / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    pre_commit = hooks / "pre-commit"
    if not pre_commit.exists():
        pre_commit.write_text(
            "#!/usr/bin/env sh\n"
            "set -eu\n"
            "if command -v python >/dev/null 2>&1; then\n"
            "  python -m compileall . >/dev/null\n"
            "fi\n",
            encoding="utf-8",
        )
        pre_commit.chmod(0o755)
    commit_msg = hooks / "commit-msg"
    if not commit_msg.exists():
        commit_msg.write_text(
            "#!/usr/bin/env sh\n"
            "set -eu\n"
            "msg_file=\"$1\"\n"
            "chars=$(wc -c < \"$msg_file\")\n"
            "if [ \"$chars\" -lt 8 ]; then\n"
            "  echo 'Commit message is too short.' >&2\n"
            "  exit 1\n"
            "fi\n",
            encoding="utf-8",
        )
        commit_msg.chmod(0o755)


def load_project(root: Path) -> ProjectSpec:
    data = read_json(project_paths(root).project_json)
    return ProjectSpec(**data)


def load_tasks(root: Path) -> list[TaskItem]:
    data = read_json(project_paths(root).tasks_json)
    return [TaskItem(**item) for item in data.get("tasks", [])]


def save_tasks(root: Path, tasks: list[TaskItem]) -> None:
    write_json(project_paths(root).tasks_json, {"tasks": [asdict(task) for task in tasks]})
    (root / "TASKS.md").write_text(render_tasks(tasks), encoding="utf-8")


def update_task_status(root: Path, task_id: str, status: str, notes: str = "") -> TaskItem:
    tasks = load_tasks(root)
    updated: list[TaskItem] = []
    found: TaskItem | None = None
    for task in tasks:
        if task.id == task_id:
            found = TaskItem(task.id, task.title, normalize_task_status(status), task.owner, task.verification, notes or task.notes)
            updated.append(found)
        else:
            updated.append(task)
    if found is None:
        raise ValueError(f"Unknown task id: {task_id}")
    save_tasks(root, updated)
    append_jsonl(project_paths(root).decisions_jsonl, {"time": _now(), "type": "task_status", "task": asdict(found)})
    return found


def normalize_task_status(status: str) -> TaskStatus:
    value = status.strip().lower()
    valid = {"todo", "in_progress", "blocked", "needs_user", "done", "verified"}
    if value not in valid:
        raise ValueError(f"Invalid task status '{status}'. Expected one of: {', '.join(sorted(valid))}")
    return value  # type: ignore[return-value]


def add_tool(root: Path, tool: ToolItem) -> None:
    paths = project_paths(root)
    data = read_json(paths.tools_json) if paths.tools_json.exists() else {"tools": []}
    tools = [item for item in data.get("tools", []) if item.get("name") != tool.name]
    tools.append(asdict(tool))
    write_json(paths.tools_json, {"tools": tools})
    append_jsonl(paths.decisions_jsonl, {"time": _now(), "type": "tool_registered", "tool": asdict(tool)})


def add_research_note(root: Path, *, topic: str, source: str, summary: str, decision: str = "") -> Path:
    paths = project_paths(root)
    paths.research_dir.mkdir(parents=True, exist_ok=True)
    path = paths.research_dir / f"{slugify(topic)}.md"
    block = "\n".join(
        [
            f"# Research: {topic}",
            "",
            f"Updated: {_now()}",
            "",
            "## Source",
            "",
            source or "Manual note",
            "",
            "## Summary",
            "",
            summary,
            "",
            "## Decision / Next Step",
            "",
            decision or "Not decided yet.",
            "",
        ]
    )
    path.write_text(block, encoding="utf-8")
    append_jsonl(
        paths.decisions_jsonl,
        {"time": _now(), "type": "research_note", "topic": topic, "source": source, "path": str(path.relative_to(root))},
    )
    return path


def verify_project(root: Path) -> VerificationResult:
    paths = project_paths(root)
    checks: list[str] = []
    missing: list[str] = []
    warnings: list[str] = []
    required_files = [
        paths.project_json,
        paths.tasks_json,
        paths.workflow_json,
        paths.tools_json,
        paths.artifacts_json,
        root / "PROJECT_SPEC.md",
        root / "TASKS.md",
        root / "WORKFLOW.md",
        root / "AGENTS.md",
    ]
    for path in required_files:
        if path.exists():
            checks.append(f"exists: {path.relative_to(root)}")
        else:
            missing.append(f"missing: {path.relative_to(root)}")

    if paths.tasks_json.exists():
        tasks = load_tasks(root)
        open_tasks = [task for task in tasks if task.status in {"todo", "in_progress", "needs_user"}]
        blocked = [task for task in tasks if task.status == "blocked"]
        if open_tasks:
            warnings.append(f"open tasks: {len(open_tasks)}")
        if blocked:
            warnings.append(f"blocked tasks: {len(blocked)}")
        if not open_tasks and not blocked:
            checks.append("tasks are done or verified")

    if paths.final_report.exists():
        checks.append("final report exists")
    else:
        warnings.append("final report not created yet")

    ok = not missing and not any(item.startswith("open tasks") for item in warnings)
    return VerificationResult(ok=ok, checks=checks, missing=missing, warnings=warnings)


def write_final_report(root: Path, *, notes: str = "") -> Path:
    spec = load_project(root)
    tasks = load_tasks(root)
    verification = verify_project(root)
    paths = project_paths(root)
    lines = [
        f"# Final Report: {spec.name}",
        "",
        f"Generated: {_now()}",
        "",
        "## Goal",
        "",
        spec.goal,
        "",
        "## Deliverables",
        "",
        *[f"- {item}" for item in spec.deliverables],
        "",
        "## Task Status",
        "",
        *[f"- {task.id} `{task.status}` {task.title}" for task in tasks],
        "",
        "## Verification",
        "",
        f"Overall: {'PASS' if verification.ok else 'NEEDS WORK'}",
        "",
        "### Checks",
        "",
        *([f"- {item}" for item in verification.checks] or ["- No checks recorded."]),
        "",
        "### Missing",
        "",
        *([f"- {item}" for item in verification.missing] or ["- None."]),
        "",
        "### Warnings",
        "",
        *([f"- {item}" for item in verification.warnings] or ["- None."]),
        "",
        "## Notes",
        "",
        notes or "No additional notes.",
        "",
    ]
    paths.final_report.write_text("\n".join(lines), encoding="utf-8")
    append_jsonl(paths.decisions_jsonl, {"time": _now(), "type": "final_report", "path": "FINAL_REPORT.md"})
    return paths.final_report


def next_action(root: Path) -> str:
    if not project_paths(root).project_json.exists():
        return "No project exists yet. Run `cagent init-project --workspace . --name ... --goal ...`."
    tasks = load_tasks(root)
    for task in tasks:
        if task.status in {"todo", "in_progress", "needs_user"}:
            return f"Next task: {task.id} ({task.owner}) - {task.title} [{task.status}]"
    blocked = [task for task in tasks if task.status == "blocked"]
    if blocked:
        return f"Project has blocked tasks: {', '.join(task.id for task in blocked)}"
    return "All tasks are done or verified. Run `cagent final-report` and `cagent verify`."


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def append_jsonl(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(data, ensure_ascii=False, sort_keys=True) + "\n")
