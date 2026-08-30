from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any


def mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def list_values(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def is_sha256(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(
        character in "0123456789abcdef" for character in text
    )


def canonical_digest(value: Any) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def digest_matches(value: Any, recorded: Any) -> bool:
    return is_sha256(recorded) and canonical_digest(value) == str(recorded)
