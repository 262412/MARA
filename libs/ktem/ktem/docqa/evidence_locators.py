from __future__ import annotations

from typing import Any


def source_alias_values(
    item: dict[str, Any],
    metadata: dict[str, Any],
    source_id: str,
) -> list[str]:
    source_aliases = item.get("source_aliases") or metadata.get("source_aliases") or []
    if isinstance(source_aliases, str):
        source_aliases = [source_aliases]
    values = [
        source_id,
        item.get("source_name"),
        item.get("file_name"),
        metadata.get("source_name"),
        metadata.get("file_name"),
        *source_aliases,
    ]
    aliases: list[str] = []
    for raw in values:
        value = str(raw or "").strip().split("#", 1)[0]
        if not value:
            continue
        filename = value.rsplit("/", 1)[-1]
        stem = filename.rsplit(".", 1)[0]
        for alias in (value, filename, stem):
            if alias and alias not in aliases:
                aliases.append(alias)
    return aliases


def merged_locator_metadata(
    evidence_metadata: dict[str, Any],
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    derived = _selected_locator_metadata(items)
    metadata: dict[str, Any] = {
        key: values or _coerce_locator_values(evidence_metadata.get(key))
        for key, values in derived.items()
    }
    metadata["source_page_locators"] = [
        {"source_id": source, "page_label": page}
        for source, page in sorted(
            set().union(*(_primary_source_page_locators(item) for item in items))
        )
        if source and page
    ]
    metadata["source_page_alias_locators"] = [
        {"source_id": source, "page_label": page}
        for source, page in sorted(
            set().union(*(normalized_source_page_locators(item) for item in items))
        )
        if source and page
    ]
    return metadata


def _selected_locator_metadata(items: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {
        "page_coverage": _unique_selected(_item_page_labels(item) for item in items),
        "source_ids": _unique_selected(_item_source_ids(item) for item in items),
        "evidence_ids": _unique_selected(
            [[str(item.get("evidence_id") or "").strip()] for item in items]
        ),
    }


def _coerce_locator_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, (list, tuple, set)):
        return []
    return _unique_selected([value])


def _unique_selected(values: Any) -> list[str]:
    output: list[str] = []
    for group in values:
        for value in group:
            item = str(value or "").strip()
            if item and item not in output:
                output.append(item)
    return output


def _item_page_labels(item: dict[str, Any]) -> list[str]:
    labels = [str(item.get("page_label") or "").strip()]
    labels.extend(
        _page_label_from_backref(ref) for ref in _backref_values(item, _metadata(item))
    )
    return labels


def _item_source_ids(item: dict[str, Any]) -> list[str]:
    source_ids = [str(item.get("source_id") or "").strip()]
    source_ids.extend(
        _source_id_from_backref(ref) for ref in _backref_values(item, _metadata(item))
    )
    return source_ids


def normalized_source_aliases(item: dict[str, Any]) -> set[str]:
    metadata = _metadata(item)
    values: list[Any] = []
    for key in (
        "source_id",
        "document_id",
        "file_id",
        "runtime_source_id",
        "source_name",
        "file_name",
        "source_aliases",
    ):
        values.extend(_values(item.get(key)))
        values.extend(_values(metadata.get(key)))
    values.extend(source for source, _page in _backref_locators(item, metadata))
    return {alias for value in values for alias in _source_variants(value) if alias}


def normalized_page_aliases(item: dict[str, Any]) -> set[str]:
    metadata = _metadata(item)
    values: list[Any] = []
    for key in (
        "page_label",
        "page",
        "page_number",
        "page_num",
        "dataset_page",
        "parser_page_index",
        "page_aliases",
    ):
        values.extend(_values(item.get(key)))
        values.extend(_values(metadata.get(key)))
    values.extend(page for _source, page in _backref_locators(item, metadata))
    return {alias for value in values for alias in _source_variants(value) if alias}


def normalized_element_labels(
    item: dict[str, Any],
    *,
    kind: str = "element",
) -> set[str]:
    metadata = _metadata(item)
    keys = {
        "element": ("element_id",),
        "figure": ("figure_label", "figure_id", "element_id"),
        "table": ("table_label", "table_id", "element_id"),
    }.get(kind, ("element_id",))
    values = [
        value
        for key in keys
        for value in (*_values(item.get(key)), *_values(metadata.get(key)))
    ]
    return {_normalized(value) for value in values if _normalized(value)}


def normalized_source_page_locators(
    item: dict[str, Any],
) -> set[tuple[str, str]]:
    metadata = _metadata(item)
    sources = _direct_source_aliases(item, metadata)
    pages = _direct_page_aliases(item, metadata)
    locators = {(source, page) for source in sources for page in pages}
    locators.update(_backref_locators(item, metadata))
    if not pages:
        locators.update((source, "") for source in sources)
    if not sources:
        locators.update(("", page) for page in pages)
    return {(source, page) for source, page in locators if source or page}


def _primary_source_page_locators(
    item: dict[str, Any],
) -> set[tuple[str, str]]:
    metadata = _metadata(item)
    source = _first_normalized(
        item,
        metadata,
        "source_id",
        "document_id",
        "file_id",
        "runtime_source_id",
    )
    page = _first_normalized_page(
        item,
        metadata,
        "page_label",
        "page",
        "page_number",
        "dataset_page",
    )
    output = {(source, page)} if source and page else set()
    output.update(_backref_locators(item, metadata))
    return output


def _direct_source_aliases(
    item: dict[str, Any],
    metadata: dict[str, Any],
) -> set[str]:
    values: list[Any] = []
    for key in (
        "source_id",
        "document_id",
        "file_id",
        "runtime_source_id",
        "source_name",
        "file_name",
        "source_aliases",
    ):
        values.extend(_values(item.get(key)))
        values.extend(_values(metadata.get(key)))
    return {_normalized_page(value) for value in values if _normalized_page(value)}


def _direct_page_aliases(
    item: dict[str, Any],
    metadata: dict[str, Any],
) -> set[str]:
    values: list[Any] = []
    for key in (
        "page_label",
        "page",
        "page_number",
        "page_num",
        "dataset_page",
        "page_aliases",
    ):
        values.extend(_values(item.get(key)))
        values.extend(_values(metadata.get(key)))
    return {_normalized_page(value) for value in values if _normalized_page(value)}


def locator_matches(
    item: dict[str, Any],
    *,
    source_id: str = "",
    page_label: str = "",
    page_labels: tuple[str, ...] = (),
    element_id: str = "",
    figure_label: str = "",
    table_label: str = "",
) -> bool:
    expected = {
        "source": _normalized(source_id),
        "page": _normalized_page(page_label),
        "element": _normalized(element_id),
        "figure": _normalized(figure_label),
        "table": _normalized(table_label),
    }
    if expected["source"] and not _matches_any(
        expected["source"], normalized_source_aliases(item)
    ):
        return False
    expected_pages = {
        _normalized_page(value)
        for value in (page_label, *page_labels)
        if _normalized_page(value)
    }
    actual_pages = normalized_page_aliases(item)
    if expected_pages and not any(
        _matches_any(expected_page, actual_pages) for expected_page in expected_pages
    ):
        return False
    for kind in ("element", "figure", "table"):
        if expected[kind] and not _matches_any(
            expected[kind],
            normalized_element_labels(item, kind=kind),
        ):
            return False
    return True


def locator_requirement_count(
    *,
    source_id: str = "",
    page_label: str = "",
    page_labels: tuple[str, ...] = (),
    element_id: str = "",
    figure_label: str = "",
    table_label: str = "",
) -> int:
    return sum(
        bool(_normalized(value))
        for value in (source_id, element_id, figure_label, table_label)
    ) + int(bool(page_label or page_labels))


def _backref_locators(
    item: dict[str, Any],
    metadata: dict[str, Any],
) -> set[tuple[str, str]]:
    output: set[tuple[str, str]] = set()
    for raw in _backref_values(item, metadata):
        value = str(raw or "").strip()
        if "#page:" in value:
            source, page = value.split("#page:", 1)
            output.add((_normalized(source), _normalized_page(page.split("#", 1)[0])))
        elif "#source" in value:
            output.add((_normalized(value.split("#source", 1)[0]), ""))
    return output


def _backref_values(
    item: dict[str, Any],
    metadata: dict[str, Any],
) -> list[Any]:
    return [
        *_values(item.get("source_backrefs")),
        *_values(metadata.get("source_backrefs")),
    ]


def _page_label_from_backref(value: Any) -> str:
    source_ref = str(value or "").strip()
    if "#page:" not in source_ref:
        return ""
    return source_ref.split("#page:", 1)[1].split("#", 1)[0].strip()


def _source_id_from_backref(value: Any) -> str:
    source_ref = str(value or "").strip()
    if "#" not in source_ref:
        return ""
    return source_ref.split("#", 1)[0].strip()


def _matches_any(expected: str, actual: set[str]) -> bool:
    return any(
        value == expected
        or value.endswith(f"-{expected}")
        or value.endswith(f":{expected}")
        for value in actual
    )


def _metadata(item: dict[str, Any]) -> dict[str, Any]:
    metadata = item.get("metadata")
    return dict(metadata) if isinstance(metadata, dict) else {}


def _first_normalized(
    item: dict[str, Any],
    metadata: dict[str, Any],
    *keys: str,
) -> str:
    for key in keys:
        value = item.get(key)
        if value in (None, ""):
            value = metadata.get(key)
        if value not in (None, ""):
            return _normalized(value)
    return ""


def _first_normalized_page(
    item: dict[str, Any],
    metadata: dict[str, Any],
    *keys: str,
) -> str:
    for key in keys:
        value = item.get(key)
        if value in (None, ""):
            value = metadata.get(key)
        if value not in (None, ""):
            return _normalized_page(value)
    return ""


def _values(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _normalized(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalized_page(value: Any) -> str:
    normalized = _normalized(value)
    try:
        numeric = float(normalized)
    except ValueError:
        return normalized
    return str(int(numeric)) if numeric.is_integer() else normalized


def _source_variants(value: Any) -> set[str]:
    normalized = _normalized(value).split("#", 1)[0]
    if not normalized:
        return set()
    filename = normalized.rsplit("/", 1)[-1]
    stem = filename.rsplit(".", 1)[0]
    return {variant for variant in (normalized, filename, stem) if variant}
