from cagent.agent import parse_action


def test_parse_plain_json_action():
    parsed = parse_action('{"tool":"finish","args":{"message":"done"}}')
    assert parsed["tool"] == "finish"
    assert parsed["args"]["message"] == "done"


def test_parse_fenced_json_action():
    parsed = parse_action('```json\n{"tool":"list_files","args":{"path":"."}}\n```')
    assert parsed == {"tool": "list_files", "args": {"path": "."}}
