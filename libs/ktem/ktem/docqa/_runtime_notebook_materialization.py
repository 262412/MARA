"""Filesystem materialization for already-authorized notebook notes."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_SAFE_PATH_PART_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _unique_text(values: Any) -> list[str]:
    items = values if isinstance(values, list) else [values]
    result: list[str] = []
    for value in items:
        item = str(value or "").strip()
        if item and item not in result:
            result.append(item)
    return result


def _title_from_note(note: dict[str, Any]) -> str:
    title = str(note.get("title") or "").strip()
    if title:
        return title
    first_line = str(note.get("text") or "").strip().splitlines()[0:1]
    return first_line[0][:80] if first_line else "Untitled note"


def _safe_path_part(value: str, fallback: str) -> str:
    normalized = _SAFE_PATH_PART_RE.sub("-", str(value or "").strip()).strip(".-")
    return (normalized or fallback)[:80]


def note_source_markdown(conversation_id: str, note: dict[str, Any]) -> str:
    """Render a stable Markdown source for one authorized note record."""
    citation_refs = _unique_text(note.get("citation_refs", []))
    metadata = [
        f"Conversation: {conversation_id}",
        f"Note ID: {note.get('note_id', '')}",
        f"Source: {note.get('source', '')}",
        "Citation refs: " + (", ".join(citation_refs) if citation_refs else "(none)"),
    ]
    return "\n".join(
        [
            f"# {_title_from_note(note)}",
            "",
            *metadata,
            "",
            str(note.get("text") or "").strip(),
            "",
        ]
    )


def default_note_sources_dir() -> Path:
    from theflow.settings import settings as flowsettings

    return Path(getattr(flowsettings, "KH_APP_DATA_DIR", Path.cwd())) / "mara_notes"


def materialize_note_source(
    conversation_id: str,
    note: dict[str, Any],
    root_dir: str | Path | None = None,
) -> str:
    """Write one authorized note beneath its conversation namespace."""
    source_root = Path(root_dir) if root_dir is not None else default_note_sources_dir()
    conversation_part = _safe_path_part(conversation_id, "conversation")
    note_part = _safe_path_part(str(note.get("note_id") or ""), "note")
    source_path = source_root / conversation_part / f"mara-note-{note_part}.md"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(
        note_source_markdown(conversation_id, note), encoding="utf-8"
    )
    return source_path.resolve().as_posix()


__all__ = [
    "default_note_sources_dir",
    "materialize_note_source",
    "note_source_markdown",
]
