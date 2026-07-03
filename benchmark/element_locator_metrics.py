from __future__ import annotations


def element_locator_hit_score(
    retrieved_hits: list[dict[str, object]],
    gold_evidence: list[dict[str, object]],
) -> float | None:
    gold_refs = _gold_element_locator_refs(gold_evidence)
    if not gold_refs:
        return None
    return float(
        any(
            _retrieved_hit_matches_gold_locator(hit, gold_ref)
            for hit in retrieved_hits
            for gold_ref in gold_refs
        )
    )


def _gold_element_locator_refs(
    gold_evidence: list[dict[str, object]],
) -> list[dict[str, set[str]]]:
    refs: list[dict[str, set[str]]] = []
    for item in gold_evidence:
        sources = _locator_sources(item)
        pages = _locator_pages(item)
        if not sources or not pages:
            continue
        refs.append(
            {
                "sources": sources,
                "pages": pages,
                "element_ids": _locator_element_ids(item),
                "element_types": _locator_element_types(item),
            }
        )
    return refs


def _retrieved_hit_matches_gold_locator(
    hit: dict[str, object],
    gold_ref: dict[str, set[str]],
) -> bool:
    if not (_locator_sources(hit) & gold_ref["sources"]):
        return False
    if not (_locator_pages(hit) & gold_ref["pages"]):
        return False
    gold_ids = gold_ref["element_ids"]
    if gold_ids and _locator_element_ids(hit) & gold_ids:
        return True
    gold_types = gold_ref["element_types"]
    return not gold_types or bool(_locator_element_types(hit) & gold_types)


def _locator_sources(item: dict[str, object]) -> set[str]:
    values = {
        item.get("document_id"),
        item.get("source_id"),
        item.get("file_id"),
        item.get("file_name"),
        item.get("source_name"),
        item.get("citation"),
    }
    for ref in _iter_list_values(item.get("source_backrefs")):
        values.add(ref.split("#", 1)[0])
    return {_normalize_locator_source(value) for value in values} - {""}


def _locator_pages(item: dict[str, object]) -> set[str]:
    pages = {item.get("page"), item.get("page_label"), item.get("page_number")}
    citation = str(item.get("citation") or "")
    if "#page:" in citation:
        pages.add(citation.rsplit("#page:", 1)[-1])
    for ref in _iter_list_values(item.get("source_backrefs")):
        if "#page:" in ref:
            pages.add(ref.rsplit("#page:", 1)[-1])
    return {_normalize_locator_page(value) for value in pages} - {""}


def _locator_element_ids(item: dict[str, object]) -> set[str]:
    values = [item.get("element_id"), item.get("element")]
    values.extend(_iter_list_values(item.get("element_id_aliases")))
    return {str(value or "").strip() for value in values if str(value or "").strip()}


def _locator_element_types(item: dict[str, object]) -> set[str]:
    values = [
        item.get("element_type"),
        item.get("modality"),
        item.get("type"),
        item.get("kind"),
        item.get("category"),
        item.get("content_type"),
    ]
    values.extend(_iter_list_values(item.get("element_type_aliases")))
    return {_normalize_locator_type(value) for value in values} - {""}


def _iter_list_values(value: object) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item).strip()]
    return []


def _normalize_locator_source(value: object) -> str:
    text = str(value or "").strip().lower()
    if "#" in text:
        text = text.split("#", 1)[0]
    text = text.rsplit("/", 1)[-1]
    return text.removesuffix(".pdf")


def _normalize_locator_page(value: object) -> str:
    text = str(value or "").strip().lower()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _normalize_locator_type(value: object) -> str:
    element_type = str(value or "").strip().lower().replace("-", "_")
    if element_type in {"image", "fig", "chart", "plot"}:
        return "figure"
    return element_type
