from cagent.repomap import build_context_pack, build_repo_map, format_context_pack, format_repo_map


def test_build_repo_map_extracts_python_symbols_and_imports(tmp_path):
    source = tmp_path / "app.py"
    source.write_text(
        "import os\nfrom pathlib import Path\n\nclass Runner:\n    pass\n\ndef main():\n    return Path.cwd()\n",
        encoding="utf-8",
    )

    files = build_repo_map(tmp_path, query="runner path", max_files=10)

    assert len(files) == 1
    assert files[0].path == "app.py"
    assert files[0].language == "python"
    assert "Runner" in files[0].symbols
    assert "main" in files[0].symbols
    assert any("pathlib" in item for item in files[0].imports)
    assert files[0].score > 0


def test_repo_map_ranks_query_matches(tmp_path):
    (tmp_path / "auth_service.py").write_text("def login_user():\n    pass\n", encoding="utf-8")
    (tmp_path / "billing.py").write_text("def invoice():\n    pass\n", encoding="utf-8")

    files = build_repo_map(tmp_path, query="login auth", max_files=10)

    assert files[0].path == "auth_service.py"
    assert files[0].score > files[1].score


def test_format_repo_map_is_compact(tmp_path):
    (tmp_path / "worker.py").write_text("def run_worker():\n    pass\n", encoding="utf-8")

    output = format_repo_map(build_repo_map(tmp_path, query="worker"))

    assert "worker.py" in output
    assert "run_worker" in output


def test_context_pack_contains_selected_file_content(tmp_path):
    (tmp_path / "agent.py").write_text("class CodingAgent:\n    pass\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")

    pack = build_context_pack(tmp_path, query="CodingAgent", max_files=1, max_chars=1000)
    output = format_context_pack(pack)

    assert len(pack.files) == 1
    assert pack.files[0].path == "agent.py"
    assert "--- FILE: agent.py" in output
    assert "class CodingAgent" in output


def test_context_pack_respects_max_chars(tmp_path):
    (tmp_path / "big.py").write_text("def huge():\n" + "x = 1\n" * 1000, encoding="utf-8")

    pack = build_context_pack(tmp_path, query="huge", max_files=1, max_chars=250)

    assert pack.truncated
    assert len(pack.content) <= 300
