"""Strict HTML sanitization for document and model-controlled UI fragments."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

import nh3

ALLOWED_TAGS = {
    "a",
    "b",
    "blockquote",
    "br",
    "code",
    "del",
    "details",
    "div",
    "em",
    "figcaption",
    "figure",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "i",
    "img",
    "li",
    "mark",
    "ol",
    "p",
    "pre",
    "span",
    "strong",
    "sub",
    "summary",
    "sup",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "ul",
}

ALLOWED_ATTRIBUTES = {
    "a": {
        "class",
        "data-page",
        "data-phrase",
        "data-search",
        "data-src",
        "href",
        "id",
        "title",
    },
    "code": {"class"},
    "details": {"class", "open"},
    "div": {"aria-label", "class", "role", "tabindex"},
    "img": {"alt", "class", "src", "title"},
    "mark": {"class", "id"},
    "span": {"class", "data-ktem-display", "data-ktem-latex"},
    "td": {"align", "colspan", "rowspan"},
    "th": {"align", "colspan", "rowspan"},
}

ALLOWED_CLASS_NAMES = {
    "citation",
    "evidence",
    "evidence-content",
    "highlight",
    "ktem-answer-chart-scroll",
    "ktem-answer-table-scroll",
    "ktem-math-source",
    "ktem-math-source--display",
    "pdf-link",
    "selected",
}
_SAFE_DATA_IMAGE_RE = re.compile(
    r"^data:image/(?:png|jpeg|gif|webp);base64,[a-z0-9+/=\s]+$", re.IGNORECASE
)
_SAFE_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$")


def _safe_link_or_image_url(tag: str, attribute: str, value: str) -> str | None:
    normalized = value.strip()
    lowered = normalized.lower()
    if lowered.startswith("data:"):
        if (
            tag == "img"
            and attribute == "src"
            and _SAFE_DATA_IMAGE_RE.fullmatch(normalized)
        ):
            return normalized
        return None
    scheme = urlsplit(normalized).scheme.lower()
    if scheme and scheme not in {"http", "https", "mailto"}:
        return None
    return normalized


def _safe_preview_source(value: str) -> str | None:
    normalized = value.strip()
    if normalized.startswith("/"):
        return normalized
    parsed = urlsplit(normalized)
    if parsed.scheme.lower() in {"http", "https"}:
        return normalized
    return None


def _attribute_filter(tag: str, attribute: str, value: str) -> str | None:
    if attribute == "class":
        classes = [
            item
            for item in value.split()
            if item in ALLOWED_CLASS_NAMES or item.startswith("language-")
        ]
        return " ".join(classes) or None
    if attribute in {"href", "src", "xlink:href"}:
        return _safe_link_or_image_url(tag, attribute, value)
    if attribute == "data-src":
        return _safe_preview_source(value)
    if attribute == "data-page":
        return value if value.isdigit() and int(value) > 0 else None
    if attribute == "data-phrase":
        return value if value in {"true", "false"} else None
    if attribute == "role":
        return value if value == "region" else None
    if attribute == "tabindex":
        return value if value == "0" else None
    if attribute == "aria-label":
        return value if value in {"Scrollable chart", "Scrollable table"} else None
    if attribute == "id":
        return value if _SAFE_ID_RE.fullmatch(value) else None
    return value


def sanitize_html(value: object) -> str:
    """Return an allowlisted HTML fragment with active content removed."""
    return nh3.clean(
        str(value or ""),
        tags=ALLOWED_TAGS,
        clean_content_tags={"embed", "iframe", "object", "script", "style", "template"},
        attributes=ALLOWED_ATTRIBUTES,
        attribute_filter=_attribute_filter,
        url_schemes={"data", "http", "https", "mailto"},
        strip_comments=True,
        link_rel="noopener noreferrer",
    )
