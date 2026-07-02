from cagent.mcp_manifest import build_manifest, manifest_json


def test_manifest_contains_snapshot_capability():
    manifest = build_manifest()
    names = {item["name"] for item in manifest["capabilities"]}

    assert "snapshot" in names


def test_manifest_contains_project_resources():
    manifest = build_manifest()
    uris = {item["uri"] for item in manifest["resources"]}

    assert "cagent://project/spec" in uris
    assert "cagent://project/tasks" in uris
    assert "cagent://project/snapshot" in uris


def test_manifest_contains_role_templates():
    manifest = build_manifest()
    names = {item["name"] for item in manifest["role_templates"]}

    assert "cagent.planner" in names
    assert "cagent.reviewer" in names


def test_manifest_json_is_valid_json_text():
    text = manifest_json()

    assert text.endswith("\n")
    assert '"capabilities"' in text
    assert '"resources"' in text
    assert '"role_templates"' in text
