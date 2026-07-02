from cagent.stdio_server import call_tool, tool_to_dict, TOOLS


def test_tools_include_config_capability():
    names = {tool_to_dict(tool)["name"] for tool in TOOLS}

    assert "cagent.config" in names


def test_config_capability_returns_runtime_json(tmp_path):
    result = call_tool(
        {
            "name": "cagent.config",
            "arguments": {
                "workspace": str(tmp_path),
                "model_role": "fast",
            },
        }
    )

    content = result["content"][0]
    payload = content["json"]

    assert content["type"] == "json"
    assert payload["workspace"] == str(tmp_path.resolve())
    assert payload["model_role"] == "fast"
    assert payload["model"] == payload["model_profiles"]["fast"]
