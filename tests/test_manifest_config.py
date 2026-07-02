from cagent.mcp_manifest import build_manifest


def test_manifest_contains_config_capability():
    manifest = build_manifest()
    names = {item["name"] for item in manifest["capabilities"]}

    assert "config" in names
