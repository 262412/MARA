from __future__ import annotations

import re
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Any

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _serialize_value(value: Any) -> Any:
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    indirect_ref = _pypdf_indirect_object_ref(value)
    if indirect_ref:
        return indirect_ref
    if isinstance(value, dict):
        return {str(key): _serialize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize_value(item) for item in value]
    return value


def _pypdf_indirect_object_ref(value: Any) -> str:
    if value.__class__.__name__ != "IndirectObject":
        return ""
    if not str(value.__class__.__module__).startswith("pypdf."):
        return ""
    idnum = getattr(value, "idnum", None)
    generation = getattr(value, "generation", None)
    if idnum is None or generation is None:
        return ""
    return f"IndirectObject({idnum}, {generation})"


def _html_to_text(value: str) -> str:
    if not value:
        return ""
    text = _HTML_TAG_RE.sub(" ", str(value))
    return " ".join(unescape(text).split()).strip()
