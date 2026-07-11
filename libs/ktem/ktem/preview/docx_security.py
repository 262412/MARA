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

    def checkpoint(self) -> tuple[int, int]:
        return self.count, self.decoded_bytes

    def restore(self, checkpoint: tuple[int, int]) -> None:
        self.count, self.decoded_bytes = checkpoint


class DocxHtmlBudgetExceeded(RuntimeError):
    """Raised before allocating markup that cannot fit in the HTML budget."""


@dataclass
class DocxHtmlBudget:
    limit: int = MAX_RENDERED_HTML_CHARS
    used: int = 0

    @property
    def remaining(self) -> int:
        return self.limit - self.used

    def checkpoint(self) -> int:
        return self.used

    def restore(self, checkpoint: int) -> None:
        self.used = checkpoint

    def reserve(self, char_count: int) -> None:
        if not self.try_reserve(char_count):
            raise DocxHtmlBudgetExceeded

    def try_reserve(self, char_count: int) -> bool:
        if char_count < 0 or char_count > self.remaining:
            return False
        self.used += char_count
        return True


def escaped_html_length(value: str, *, quote: bool = True) -> int:
    length = len(value)
    length += value.count("&") * 4
    length += (value.count("<") + value.count(">")) * 3
    if quote:
        length += value.count('"') * 5
        length += value.count("'") * 4
    return length


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
    html_budget: DocxHtmlBudget | None = None,
    rendered_html_chars: int = 0,
) -> str:
    mime_type = str(content_type or "").strip().lower()
    if mime_type not in SAFE_RASTER_MIME_TYPES:
        return ""
    if not payload or len(payload) > max_decoded_bytes:
        return ""
    if not _matches_raster_signature(mime_type, payload):
        return ""
    html_checkpoint = html_budget.checkpoint() if html_budget is not None else 0
    encoded_length = 4 * ((len(payload) + 2) // 3)
    data_url_length = len(f"data:{mime_type};base64,") + encoded_length
    if html_budget is not None and not html_budget.try_reserve(
        rendered_html_chars + data_url_length
    ):
        return ""
    if budget is not None and not budget.try_consume(len(payload)):
        if html_budget is not None:
            html_budget.restore(html_checkpoint)
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
    "DocxHtmlBudget",
    "DocxHtmlBudgetExceeded",
    "DocxImageBudget",
    "MAX_AGGREGATE_IMAGE_BYTES",
    "MAX_EMBEDDED_IMAGE_BYTES",
    "MAX_EMBEDDED_IMAGE_COUNT",
    "MAX_RENDERED_HTML_CHARS",
    "SAFE_HYPERLINK_SCHEMES",
    "SAFE_RASTER_MIME_TYPES",
    "escaped_html_length",
    "escape",
    "safe_font",
    "safe_hyperlink_target",
    "safe_raster_data_url",
]
