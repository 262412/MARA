from __future__ import annotations

import base64
from dataclasses import dataclass
from html import escape
from urllib.parse import urlsplit

SAFE_HYPERLINK_SCHEMES = frozenset({"http", "https", "mailto"})
SAFE_RASTER_MIME_TYPES = frozenset(
    {"image/gif", "image/jpeg", "image/png", "image/webp"}
)
MAX_EMBEDDED_IMAGE_BYTES = 5 * 1024 * 1024
MAX_EMBEDDED_IMAGE_COUNT = 16
MAX_AGGREGATE_IMAGE_BYTES = 5 * 1024 * 1024
MAX_RENDERED_HTML_CHARS = 8 * 1024 * 1024


@dataclass
class DocxImageBudget:
    count: int = 0
    decoded_bytes: int = 0

    def try_consume(self, payload_size: int) -> bool:
        if self.count >= MAX_EMBEDDED_IMAGE_COUNT:
            return False
        if self.decoded_bytes + payload_size > MAX_AGGREGATE_IMAGE_BYTES:
            return False
        self.count += 1
        self.decoded_bytes += payload_size
        return True


def safe_font(font_name: str, fallback: str) -> str:
    candidate = str(font_name or "").strip()
    if not candidate or len(candidate) > 120:
        return fallback
    if not all(char.isalnum() or char in " .,_-" for char in candidate):
        return fallback
    return candidate


def safe_hyperlink_target(target: str) -> str:
    candidate = str(target or "")
    if not candidate or candidate != candidate.strip():
        return ""
    if any(ord(char) < 32 or ord(char) == 127 for char in candidate):
        return ""
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return ""
    scheme = parsed.scheme.lower()
    if scheme not in SAFE_HYPERLINK_SCHEMES:
        return ""
    if scheme in {"http", "https"} and not parsed.netloc:
        return ""
    if scheme == "mailto" and not parsed.path:
        return ""
    return candidate


def safe_raster_data_url(
    content_type: str,
    payload: bytes,
    *,
    max_decoded_bytes: int = MAX_EMBEDDED_IMAGE_BYTES,
    budget: DocxImageBudget | None = None,
) -> str:
    mime_type = str(content_type or "").strip().lower()
    if mime_type not in SAFE_RASTER_MIME_TYPES:
        return ""
    if not payload or len(payload) > max_decoded_bytes:
        return ""
    if not _matches_raster_signature(mime_type, payload):
        return ""
    if budget is not None and not budget.try_consume(len(payload)):
        return ""
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _matches_raster_signature(mime_type: str, payload: bytes) -> bool:
    if mime_type == "image/png":
        return payload.startswith(b"\x89PNG\r\n\x1a\n")
    if mime_type == "image/jpeg":
        return payload.startswith(b"\xff\xd8\xff")
    if mime_type == "image/gif":
        return payload.startswith((b"GIF87a", b"GIF89a"))
    if mime_type == "image/webp":
        return (
            len(payload) >= 12
            and payload.startswith(b"RIFF")
            and payload[8:12] == b"WEBP"
        )
    return False


__all__ = [
    "DocxImageBudget",
    "MAX_AGGREGATE_IMAGE_BYTES",
    "MAX_EMBEDDED_IMAGE_BYTES",
    "MAX_EMBEDDED_IMAGE_COUNT",
    "MAX_RENDERED_HTML_CHARS",
    "SAFE_HYPERLINK_SCHEMES",
    "SAFE_RASTER_MIME_TYPES",
    "escape",
    "safe_font",
    "safe_hyperlink_target",
    "safe_raster_data_url",
]
