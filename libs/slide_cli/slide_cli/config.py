from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


VALID_APPLY_MODES = {"preview", "confirm", "apply"}
VALID_APPROVAL_POLICIES = {"auto", "confirm"}


@dataclass(frozen=True, slots=True)
class SlideAgentConfig:
    cwd: str | None = None
    approval_policy: str = "confirm"
    shell_timeout_sec: int = 15
    model: str = "gpt-4o-mini"
    provider: str | None = None
    config_path: str = "modelcli.yml"
    max_iterations: int = 4
    apply_mode: str = "preview"
    output_path: str | None = None

    def __post_init__(self) -> None:
        if self.approval_policy not in VALID_APPROVAL_POLICIES:
            raise ValueError(
                f"Unsupported approval_policy '{self.approval_policy}'. "
                f"Expected one of {sorted(VALID_APPROVAL_POLICIES)}."
            )
        if self.apply_mode not in VALID_APPLY_MODES:
            raise ValueError(
                f"Unsupported apply_mode '{self.apply_mode}'. "
                f"Expected one of {sorted(VALID_APPLY_MODES)}."
            )
        if self.shell_timeout_sec <= 0:
            raise ValueError("shell_timeout_sec must be greater than zero.")
        if self.max_iterations <= 0:
            raise ValueError("max_iterations must be greater than zero.")

    @property
    def should_apply(self) -> bool:
        return self.apply_mode == "apply"

    @property
    def needs_confirmation(self) -> bool:
        return self.apply_mode == "confirm"

    def resolved_cwd(self, fallback: str | Path) -> Path:
        if self.cwd:
            return Path(self.cwd).resolve()
        return Path(fallback).resolve()

    def as_dict(self) -> dict[str, Any]:
        return {
            "cwd": self.cwd or "",
            "approval_policy": self.approval_policy,
            "shell_timeout_sec": self.shell_timeout_sec,
            "model": self.model,
            "provider": self.provider or "",
            "config_path": self.config_path,
            "max_iterations": self.max_iterations,
            "apply_mode": self.apply_mode,
            "output_path": self.output_path or "",
        }


__all__ = [
    "SlideAgentConfig",
    "VALID_APPLY_MODES",
    "VALID_APPROVAL_POLICIES",
]
