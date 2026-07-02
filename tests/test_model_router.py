import os

import pytest

from cagent.config import AgentConfig
from cagent.model_router import ModelProfiles, normalize_model_role


def test_model_profiles_resolve_roles():
    profiles = ModelProfiles(default="daily", fast="small", reviewer="large")

    assert profiles.resolve("default") == "daily"
    assert profiles.resolve("fast") == "small"
    assert profiles.resolve("reviewer") == "large"


def test_model_role_validation_rejects_unknown_role():
    with pytest.raises(ValueError, match="Invalid model role"):
        normalize_model_role("huge")


def test_config_selects_fast_model_from_cli(tmp_path):
    config = AgentConfig.from_values(
        workspace=tmp_path,
        model="daily",
        fast_model="small",
        reviewer_model="large",
        model_role="fast",
    )

    assert config.model_role == "fast"
    assert config.model == "small"
    assert config.model_profiles.default == "daily"
    assert config.model_profiles.reviewer == "large"


def test_config_selects_reviewer_model_from_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("CAGENT_MODEL", "daily")
    monkeypatch.setenv("CAGENT_FAST_MODEL", "small")
    monkeypatch.setenv("CAGENT_REVIEWER_MODEL", "large")
    monkeypatch.setenv("CAGENT_MODEL_ROLE", "reviewer")

    config = AgentConfig.from_values(workspace=tmp_path)

    assert config.model_role == "reviewer"
    assert config.model == "large"


def test_cli_values_override_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("CAGENT_MODEL_ROLE", "reviewer")
    monkeypatch.setenv("CAGENT_REVIEWER_MODEL", "env-large")

    config = AgentConfig.from_values(
        workspace=tmp_path,
        model_role="default",
        model="cli-daily",
    )

    assert config.model_role == "default"
    assert config.model == "cli-daily"


def test_model_profile_lines_mark_selected_role():
    lines = ModelProfiles(default="daily", fast="small", reviewer="large").as_lines(
        selected_role="reviewer"
    )

    assert "  * reviewer: large" in lines
    assert "  - default: daily" in lines
