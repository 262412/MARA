from __future__ import annotations

from typing import Any

from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.evidence_locators import (
    normalized_page_aliases,
    normalized_source_aliases,
)

from .citation_locators import CitationLocator


def citation_from_item(
    item: dict[str, Any],
    *,
    span: str,
    canonical_sources: list[str],
    source_backrefs: list[str],
    evidence_identity: str = "",
) -> dict[str, str]:
    page_label = first_nonempty_value(
        item.get("page_label"),
        item.get("page"),
        item.get("page_number"),
    )
    page_aliases = normalized_page_aliases(item)
    source_ref = first_nonempty_value(
        *source_backrefs,
        matching_canonical_source_ref(
            canonical_sources,
            page_label,
            source_id=first_nonempty_value(
                item.get("source_id"),
                item.get("document_id"),
                item.get("file_id"),
                item.get("runtime_source_id"),
            ),
            source_aliases=tuple(normalized_source_aliases(item)),
            page_aliases=tuple(page_aliases),
        ),
    )
    if source_ref:
        parsed = citation_from_source_ref(source_ref, span=span)
        source_id = parsed.get("source_id", "")
        page_label = parsed.get("page_label", "") or page_label
    else:
        source_id = first_nonempty_value(
            item.get("source_id"),
            item.get("document_id"),
            item.get("file_id"),
            item.get("runtime_source_id"),
        )
    if not source_id and not page_label:
        return {}
    identity = identity_of(item)
    return CitationLocator(
        kind=identity.kind,
        evidence_identity=first_nonempty_value(evidence_identity, identity.key),
        source_id=source_id,
        page_label=page_label,
        span=str(span or "").strip(),
    ).as_dict()


def matching_canonical_source_ref(
    sources: list[str],
    page_label: str,
    *,
    source_id: str = "",
    source_aliases: list[str] | tuple[str, ...] = (),
    page_aliases: list[str] | tuple[str, ...] = (),
) -> str:
    aliases = {
        str(value or "").strip().split("#", 1)[0].lower()
        for value in (source_id, *source_aliases)
        if str(value or "").strip()
    }
    pages = {
        str(value or "").strip().lower()
        for value in (page_label, *page_aliases)
        if str(value or "").strip()
    }
    candidates = [
        str(source).strip()
        for source in sources
        if str(source or "").strip()
        and (
            not pages
            or any(
                str(source).strip().lower().endswith(f"#page:{page}") for page in pages
            )
        )
    ]
    alias_matches = [
        source for source in candidates if source.split("#", 1)[0].lower() in aliases
    ]
    if len(alias_matches) == 1:
        return alias_matches[0]
    if len(candidates) == 1:
        return candidates[0]
    return ""


def citation_from_source_ref(source_ref: str, *, span: str) -> dict[str, str]:
    value = str(source_ref or "").strip()
    if not value:
        return {}
    if "#page:" in value:
        source_id, page_label = value.split("#page:", 1)
        return _citation_fields("page", source_id, page_label, span)
    if "#source" in value:
        source_id = value.split("#source", 1)[0].strip()
        return _citation_fields("source", source_id, "", span)
    return _citation_fields("source", value, "", span)


def first_nonempty_value(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _citation_fields(
    kind: str,
    source_id: str,
    page_label: str,
    span: str,
) -> dict[str, str]:
    return {
        key: value
        for key, value in {
            "kind": kind,
            "source_id": str(source_id or "").strip(),
            "page_label": str(page_label or "").strip(),
            "span": str(span or "").strip(),
        }.items()
        if value
    }
