from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ModelRequest:
    prompt: str
    model: str
    system_prompt: str | None = None
    temperature: float = 0.2
    max_tokens: int | None = None


@dataclass(slots=True)
class ModelResponse:
    text: str
    provider: str
    model: str
    raw: Any | None = None
