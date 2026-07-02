"""Runtime configuration for cagent."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from cagent.command_policy import normalize_command_profile
from cagent.model_router import (
    DEFAULT_DAILY_MODEL,
    DEFAULT_FAST_MODEL,
    DEFAULT_REVIEWER_MODEL,
    ModelProfiles,
    normalize_model_role,
)


@dataclass(frozen=True)
class AgentConfig:
    """Single immutable config object passed through the agent runtime."""

    base_url: str
    model: str
    workspace: Path
    temperature: float = 0.15
    max_tokens: int = 4096
    max_steps: int = 8
    request_timeout_seconds: int = 120
    shell_timeout_seconds: int = 30
    allow_write: bool = False
    allow_shell: bool = False
    dry_run: bool = False
    log_run: bool = False
    model_role: str = "default"
    model_profiles: ModelProfiles = ModelProfiles()
    command_profile: str = "inspect"
    auto_approve_shell: bool = False
    redact_secrets: bool = True

    @classmethod
    def from_values(
        cls,
        *,
        base_url: str | None = None,
        model: str | None = None,
        fast_model: str | None = None,
        reviewer_model: str | None = None,
        model_role: str | None = None,
        workspace: str | Path | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        max_steps: int | None = None,
        request_timeout_seconds: int | None = None,
        shell_timeout_seconds: int | None = None,
        command_profile: str | None = None,
        auto_approve_shell: bool | None = None,
        redact_secrets: bool | None = None,
        allow_write: bool = False,
        allow_shell: bool = False,
        dry_run: bool = False,
        log_run: bool | None = None,
    ) -> "AgentConfig":
        """Build config from CLI values and environment defaults."""

        selected_workspace = Path(workspace or os.environ.get("CAGENT_WORKSPACE", ".")).resolve()
        selected_workspace.mkdir(parents=True, exist_ok=True)

        profiles = ModelProfiles(
            default=model or os.environ.get("CAGENT_MODEL") or DEFAULT_DAILY_MODEL,
            fast=fast_model or os.environ.get("CAGENT_FAST_MODEL") or DEFAULT_FAST_MODEL,
            reviewer=reviewer_model or os.environ.get("CAGENT_REVIEWER_MODEL") or DEFAULT_REVIEWER_MODEL,
        )
        selected_role = normalize_model_role(model_role or os.environ.get("CAGENT_MODEL_ROLE") or "default")
        selected_model = profiles.resolve(selected_role)
        selected_command_profile = normalize_command_profile(
            command_profile or os.environ.get("CAGENT_COMMAND_PROFILE") or "inspect"
        )

        return cls(
            base_url=(base_url or os.environ.get("CAGENT_BASE_URL") or "http://127.0.0.1:18080/v1").rstrip("/"),
            model=selected_model,
            workspace=selected_workspace,
            temperature=float(temperature if temperature is not None else os.environ.get("CAGENT_TEMPERATURE", "0.15")),
            max_tokens=int(max_tokens if max_tokens is not None else os.environ.get("CAGENT_MAX_TOKENS", "4096")),
            max_steps=int(max_steps if max_steps is not None else os.environ.get("CAGENT_MAX_STEPS", "8")),
            request_timeout_seconds=int(
                request_timeout_seconds
                if request_timeout_seconds is not None
                else os.environ.get("CAGENT_REQUEST_TIMEOUT_SECONDS", "120")
            ),
            shell_timeout_seconds=int(
                shell_timeout_seconds
                if shell_timeout_seconds is not None
                else os.environ.get("CAGENT_SHELL_TIMEOUT_SECONDS", "30")
            ),
            allow_write=allow_write,
            allow_shell=allow_shell,
            dry_run=dry_run,
            log_run=_env_flag("CAGENT_LOG_RUNS", False) if log_run is None else log_run,
            model_role=selected_role,
            model_profiles=profiles,
            command_profile=selected_command_profile,
            auto_approve_shell=(
                _env_flag("CAGENT_AUTO_APPROVE_SHELL", False)
                if auto_approve_shell is None
                else auto_approve_shell
            ),
            redact_secrets=(
                _env_flag("CAGENT_REDACT_SECRETS", True)
                if redact_secrets is None
                else redact_secrets
            ),
        )


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
