"""Model profile routing for cagent.

The router is intentionally small: it does not make autonomous routing decisions
inside the agent loop yet. It resolves a named role to a concrete model so the
same endpoint can be used with fast/default/reviewer profiles.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ModelRole = Literal["default", "fast", "reviewer"]

DEFAULT_DAILY_MODEL = "qwen2.5-coder:14b-instruct-q4_K_M"
DEFAULT_FAST_MODEL = "qwen2.5-coder:7b-instruct-q4_K_M"
DEFAULT_REVIEWER_MODEL = "qwen3-coder:30b-a3b-q4_K_M"
VALID_MODEL_ROLES: tuple[ModelRole, ...] = ("default", "fast", "reviewer")


@dataclass(frozen=True)
class ModelProfiles:
    """Concrete model names for each supported role."""

    default: str = DEFAULT_DAILY_MODEL
    fast: str = DEFAULT_FAST_MODEL
    reviewer: str = DEFAULT_REVIEWER_MODEL

    def resolve(self, role: str) -> str:
        """Return the model for a role, raising a clear error for invalid roles."""

        normalized = normalize_model_role(role)
        return getattr(self, normalized)

    def as_lines(self, *, selected_role: str | None = None) -> list[str]:
        """Render profiles for CLI output."""

        selected = normalize_model_role(selected_role or "default")
        return [
            _format_line("default", self.default, selected),
            _format_line("fast", self.fast, selected),
            _format_line("reviewer", self.reviewer, selected),
        ]


def normalize_model_role(role: str | None) -> ModelRole:
    """Normalize and validate a model role string."""

    value = (role or "default").strip().lower()
    if value not in VALID_MODEL_ROLES:
        valid = ", ".join(VALID_MODEL_ROLES)
        raise ValueError(f"Invalid model role '{role}'. Expected one of: {valid}")
    return value  # type: ignore[return-value]


def _format_line(role: ModelRole, model: str, selected: ModelRole) -> str:
    marker = "*" if role == selected else "-"
    return f"  {marker} {role}: {model}"
