import json

from cagent.cli import main


def test_config_command_prints_resolved_values(tmp_path, capsys):
    code = main(
        [
            "config",
            "--workspace",
            str(tmp_path),
            "--request-retries",
            "3",
            "--retry-backoff-seconds",
            "0.25",
            "--command-profile",
            "test",
        ]
    )
    output = capsys.readouterr().out

    assert code == 0
    assert f"workspace:               {tmp_path.resolve()}" in output
    assert "request_retries:         3" in output
    assert "retry_backoff_seconds:   0.25" in output
    assert "command_profile:         test" in output


def test_config_command_prints_json(tmp_path, capsys):
    code = main(
        [
            "config",
            "--workspace",
            str(tmp_path),
            "--json",
            "--model-role",
            "fast",
        ]
    )
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert code == 0
    assert payload["workspace"] == str(tmp_path.resolve())
    assert payload["model_role"] == "fast"
    assert payload["model"] == payload["model_profiles"]["fast"]
    assert payload["redact_secrets"] is True
