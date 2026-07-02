"""Runtime configuration for cagent."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


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

    @classmethod
    def from_values(
        cls,
        *,
        base_url: str | None = None,
        model: str | None = None,
        workspace: str | Path | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        max_steps: int | None = None,
        request_timeout_seconds: int | None = None,
        shell_timeout_seconds: int | None = None,
        allow_write: bool = False,
        allow_shell: bool = False,
        dry_run: bool = False,
        log_run: bool | None = None,
    ) -> "AgentConfig":
        """Build config from CLI values and environment defaults."""

        selected_workspace = Path(workspace or os.environ.get("CAGENT_WORKSPACE", ".")).resolve()
        selected_workspace.mkdir(parents=True, exist_ok=True)

        return cls(
            base_url=(base_url or os.environ.get("CAGENT_BASE_URL") or "http://127.0.0.1:18080/v1").rstrip("/"),
            model=model or os.environ.get("CAGENT_MODEL") or "qwen2.5-coder:14b-instruct-q4_K_M",
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
        )


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
