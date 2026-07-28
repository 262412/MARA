from __future__ import annotations

from typing import Any

from ktem.docqa.evidence_identity import identity_of

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
    source_ref = first_nonempty_value(
        *source_backrefs,
        matching_canonical_source_ref(canonical_sources, page_label),
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


def matching_canonical_source_ref(sources: list[str], page_label: str) -> str:
    if page_label:
        suffix = f"#page:{page_label}"
        for source in sources:
            if str(source or "").strip().endswith(suffix):
                return str(source).strip()
    return sources[0] if sources else ""


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
