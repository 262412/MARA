from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any


class JSONLDecodeError(ValueError):
    """A JSONL record could not be decoded at a physical LF line."""

    def __init__(self, path: Path, line_number: int, cause: json.JSONDecodeError):
        super().__init__(f"invalid JSONL in {path} at line {line_number}: {cause.msg}")
        self.path = path
        self.line_number = line_number
        self.cause = cause


def iter_jsonl(path: str | Path) -> Iterator[Any]:
    """Read JSONL using physical LF boundaries, not Unicode ``splitlines``."""

    resolved = Path(path)
    with resolved.open("r", encoding="utf-8", newline="") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip(" \t\r\n"):
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise JSONLDecodeError(resolved, line_number, exc) from exc


def read_jsonl(path: str | Path) -> list[Any]:
    return list(iter_jsonl(path))
