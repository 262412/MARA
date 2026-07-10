from __future__ import annotations

import base64
from html import escape
from urllib.parse import urlsplit

SAFE_HYPERLINK_SCHEMES = frozenset({"http", "https", "mailto"})
SAFE_RASTER_MIME_TYPES = frozenset(
    {"image/gif", "image/jpeg", "image/png", "image/webp"}
)
MAX_EMBEDDED_IMAGE_BYTES = 5 * 1024 * 1024


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
) -> str:
    mime_type = str(content_type or "").strip().lower()
    if mime_type not in SAFE_RASTER_MIME_TYPES:
        return ""
    if not payload or len(payload) > max_decoded_bytes:
        return ""
    if not _matches_raster_signature(mime_type, payload):
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
    "MAX_EMBEDDED_IMAGE_BYTES",
    "SAFE_HYPERLINK_SCHEMES",
    "SAFE_RASTER_MIME_TYPES",
    "escape",
    "safe_hyperlink_target",
    "safe_raster_data_url",
]
