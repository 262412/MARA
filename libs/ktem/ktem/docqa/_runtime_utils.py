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
    if isinstance(value, dict):
        return {str(key): _serialize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize_value(item) for item in value]
    return value


def _html_to_text(value: str) -> str:
    if not value:
        return ""
    text = _HTML_TAG_RE.sub(" ", str(value))
    return " ".join(unescape(text).split()).strip()
