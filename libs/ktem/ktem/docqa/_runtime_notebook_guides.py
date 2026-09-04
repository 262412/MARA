"""Pure source-guide rendering for notebook file records."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_TOPIC_PART_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _record_value(record: Any, key: str, default: Any = "") -> Any:
    if isinstance(record, dict):
        return record.get(key, default)
    return getattr(record, key, default)


def _topics_from_name(name: str) -> list[str]:
    stem = Path(str(name or "source")).stem
    topics = [
        part
        for part in _TOPIC_PART_RE.split(stem.replace("_", " "))
        if part and not part.isdigit()
    ]
    return topics[:5] or [stem or "source"]


def build_source_guides(records: list[Any]) -> list[dict[str, Any]]:
    """Build stable notebook guide records from indexed source metadata."""
    guides: list[dict[str, Any]] = []
    for record in records:
        name = str(_record_value(record, "name", "source") or "source")
        tokens = int(_record_value(record, "tokens", 0) or 0)
        loader = str(_record_value(record, "loader", "document") or "document")
        metadata = {
            "tokens": tokens,
            "size": int(_record_value(record, "size", 0) or 0),
            "loader": loader,
            "path": str(_record_value(record, "path", "") or ""),
            "date_created": _record_value(record, "date_created", ""),
        }
        guides.append(
            {
                "source_id": str(_record_value(record, "file_id", "") or ""),
                "name": name,
                "summary": (
                    f"{name} is an indexed {loader} source with {tokens} tokens."
                ),
                "key_topics": _topics_from_name(name),
                "suggested_questions": [
                    f"What are the key points in {name}?",
                    f"Which evidence from {name} supports the answer?",
                ],
                "metadata": metadata,
            }
        )
    return guides


__all__ = ["build_source_guides"]
