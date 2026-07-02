from cagent.config import AgentConfig


def test_agent_config_accepts_retry_values(tmp_path):
    config = AgentConfig.from_values(
        workspace=tmp_path,
        request_retries=3,
        retry_backoff_seconds=0.25,
    )

    assert config.request_retries == 3
    assert config.retry_backoff_seconds == 0.25


def test_agent_config_reads_retry_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CAGENT_REQUEST_RETRIES", "4")
    monkeypatch.setenv("CAGENT_RETRY_BACKOFF_SECONDS", "0.75")

    config = AgentConfig.from_values(workspace=tmp_path)

    assert config.request_retries == 4
    assert config.retry_backoff_seconds == 0.75
