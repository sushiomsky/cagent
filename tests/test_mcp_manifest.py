from cagent.mcp_manifest import build_manifest, manifest_json


def test_manifest_contains_snapshot_capability():
    manifest = build_manifest()
    names = {item["name"] for item in manifest["capabilities"]}

    assert "snapshot" in names


def test_manifest_json_is_valid_json_text():
    text = manifest_json()

    assert text.endswith("\n")
    assert '"capabilities"' in text
