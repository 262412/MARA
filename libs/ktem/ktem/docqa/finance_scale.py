from __future__ import annotations

import re
from typing import Any

from .financial_statement_identity import source_identity


def scale_from_text(text: str, *, aliases: tuple[str, ...] = ()) -> str:
    lowered = text.lower()
    header = re.search(
        r"(?:"
        r"\(?\s*in|"
        r"dollars?\s+(?:are\s+)?(?:presented\s+)?in|"
        r"tabular\s+dollars?\s+(?:are\s+)?(?:presented\s+)?in"
        r")\s+(thousands?|millions?|billions?)\b|"
        r"\(\s*(thousands?|millions?|billions?)\s*\)",
        lowered,
    )
    if header is not None:
        return next(value for value in header.groups() if value).rstrip("s")
    for alias in aliases:
        match = re.search(
            rf"{re.escape(alias.lower())}.{{0,100}}?"
            r"(thousands?|millions?|billions?)\b",
            lowered,
        )
        if match is not None:
            return match.group(1).rstrip("s")
    return ""


def source_scale_evidence(
    item: dict[str, Any] | None,
    evidence_items: list[dict[str, Any]],
) -> tuple[str, str]:
    source_id = _source_id(item)
    item_id = _item_id(item)
    if not source_id and not item_id:
        return "", ""
    matches: list[tuple[int, int, str, str]] = []
    for candidate in evidence_items:
        if source_id and _source_id(candidate) != source_id:
            continue
        if (
            not source_id
            and _item_id(candidate) != item_id
            and (item is None or not _is_materialization_parent(item, candidate))
        ):
            continue
        if item is not None and not compatible_dimension_scope(item, candidate):
            continue
        if (
            _is_atomic_evidence(candidate)
            and _item_id(candidate) != item_id
            and candidate.get("value") not in (None, "")
        ):
            continue
        structured_scale = _item_dimension(candidate, "scale")
        text_scale = scale_from_text(_item_text(candidate))
        is_self = _item_id(candidate) == item_id
        if _is_atomic_evidence(candidate) and is_self:
            scale = (
                structured_scale
                if structured_scale
                and _explicit_scale_in_text(_item_text(candidate), structured_scale)
                else ""
            )
        else:
            scale = structured_scale or text_scale
        evidence_id = _item_id(candidate)
        if scale and evidence_id:
            matches.append(
                (
                    1 if _is_atomic_evidence(candidate) else 0,
                    _binding_distance(item, candidate),
                    scale,
                    evidence_id,
                )
            )
    if not matches:
        return "", ""
    best_rank = min((kind, distance) for kind, distance, _scale, _id in matches)
    local_matches = [
        (scale, evidence_id)
        for kind, distance, scale, evidence_id in matches
        if (kind, distance) == best_rank
    ]
    scales = {scale for scale, _evidence_id in local_matches}
    if len(scales) != 1:
        return "", ""
    scale = next(iter(scales))
    evidence_id = next(
        evidence_id
        for candidate_scale, evidence_id in local_matches
        if candidate_scale == scale
    )
    return scale, evidence_id


def _explicit_scale_in_text(text: str, scale: str) -> bool:
    return bool(
        re.search(
            rf"\b{re.escape(str(scale or '').lower())}s?\b",
            str(text or "").lower(),
        )
    )


def dimension_binding_scope(
    item: dict[str, Any] | None,
    dimension_item: dict[str, Any] | None,
) -> str:
    if item is None or dimension_item is None:
        return ""
    if (
        _item_id(item)
        and _item_id(item) == _item_id(dimension_item)
        and _item_dimension(item, "scale_provenance") == "local_currency_amount"
    ):
        return "operand_local"
    if _is_materialization_parent(item, dimension_item):
        return "table"
    if _same_table_lineage(item, dimension_item):
        return "table"
    if _same_field(item, dimension_item, "table_instance_id"):
        return "table"
    if _same_field(item, dimension_item, "table_group_id"):
        return "table_group"
    if _same_field(item, dimension_item, "page_label"):
        return "page"
    if _source_id(item) == _source_id(dimension_item):
        return "source"
    return ""


def valid_dimension_evidence_identity(value: str) -> bool:
    normalized = str(value or "").strip().lower()
    return ":" in normalized and normalized not in {"unknown", "none", "null"}


def valid_dimension_binding_scope(value: str) -> bool:
    return str(value or "").strip() in {"table", "table_group", "page", "source"}


def compatible_dimension_scope(
    item: dict[str, Any],
    dimension_item: dict[str, Any],
) -> bool:
    if _is_materialization_parent(item, dimension_item):
        return True
    if _source_id(item) != _source_id(dimension_item):
        return False
    if _page_local_scale_convention(dimension_item):
        return _same_page(item, dimension_item) or _explicit_dimension_link(
            item,
            dimension_item,
        )
    if _source_wide_scale_convention(dimension_item):
        return True
    if _same_table_lineage(item, dimension_item):
        return True
    table_instance_id = _item_dimension(item, "table_instance_id")
    dimension_table_instance_id = _item_dimension(
        dimension_item,
        "table_instance_id",
    )
    if table_instance_id or dimension_table_instance_id:
        return bool(
            table_instance_id
            and dimension_table_instance_id
            and table_instance_id == dimension_table_instance_id
        )
    table_group_id = _item_dimension(item, "table_group_id")
    dimension_table_group_id = _item_dimension(dimension_item, "table_group_id")
    if table_group_id or dimension_table_group_id:
        return bool(
            table_group_id
            and dimension_table_group_id
            and table_group_id == dimension_table_group_id
        )
    page_label = _item_dimension(item, "page_label")
    dimension_page_label = _item_dimension(dimension_item, "page_label")
    if page_label or dimension_page_label:
        return bool(
            page_label and dimension_page_label and page_label == dimension_page_label
        )
    return True


def _page_local_scale_convention(item: dict[str, Any]) -> bool:
    text = " ".join(_item_text(item).lower().split())
    return bool(
        "otherwise indicated" not in text
        and re.search(
            r"all amounts.{0,80}?following tables?.{0,40}?"
            r"(?:are\s+)?in\s+(?:thousands?|millions?|billions?)\b",
            text,
        )
    )


def _source_wide_scale_convention(item: dict[str, Any]) -> bool:
    text = " ".join(_item_text(item).lower().split())
    return bool(
        ("unless otherwise noted" in text or "otherwise indicated" in text)
        and (
            "tabular dollars" in text
            or "all dollar amounts" in text
            or "all amounts" in text
        )
    )


def _same_page(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_page = _item_dimension(left, "page_label")
    right_page = _item_dimension(right, "page_label")
    return bool(left_page and right_page and left_page == right_page)


def _explicit_dimension_link(
    item: dict[str, Any],
    dimension_item: dict[str, Any],
) -> bool:
    linked_ids = {
        str(item.get(field) or "").strip()
        for field in (
            "dimension_evidence_id",
            "dimension_source_id",
            "scale_evidence_id",
            "scale_source_id",
        )
        if str(item.get(field) or "").strip()
    }
    linked_ids.update(
        str(value).strip()
        for field in ("dimension_evidence_ids", "scale_evidence_ids")
        for value in item.get(field) or ()
        if str(value).strip()
    )
    if not linked_ids:
        return False
    return bool(linked_ids & _evidence_aliases(dimension_item))


def _evidence_aliases(item: dict[str, Any]) -> set[str]:
    return {
        str(item.get(field) or "").strip()
        for field in (
            "evidence_id",
            "canonical_id",
            "element_id",
            "cell_id",
            "span_id",
        )
        if str(item.get(field) or "").strip()
    }


def _is_materialization_parent(
    item: dict[str, Any],
    candidate: dict[str, Any],
) -> bool:
    parent_ids = {
        str(item.get(field) or "").strip()
        for field in ("materialization_source_id", "parent_element_id", "table_id")
        if str(item.get(field) or "").strip()
    }
    if not parent_ids:
        return False
    candidate_ids = {
        str(candidate.get(field) or "").strip()
        for field in (
            "evidence_id",
            "canonical_id",
            "element_id",
            "table_id",
            "table_instance_id",
        )
        if str(candidate.get(field) or "").strip()
    }
    if parent_ids & candidate_ids:
        return True
    parent_keys = {_normalized_table_key(value) for value in parent_ids}
    candidate_keys = {_normalized_table_key(value) for value in candidate_ids}
    return bool((parent_keys - {""}) & (candidate_keys - {""}))


def _same_table_lineage(
    left: dict[str, Any],
    right: dict[str, Any],
) -> bool:
    left_keys = _table_keys(left)
    right_keys = _table_keys(right)
    return bool(left_keys and right_keys and left_keys & right_keys)


def _table_keys(item: dict[str, Any]) -> set[str]:
    for fields in (
        ("table_instance_id",),
        ("table_id", "materialization_source_id", "parent_element_id"),
        ("table_group_id",),
    ):
        structured = {
            _normalized_table_key(_item_dimension(item, field)) for field in fields
        } - {""}
        if structured:
            return structured
    return {
        _normalized_table_key(str(item.get(field) or ""))
        for field in ("element_id", "evidence_id", "canonical_id")
    } - {""}


def _normalized_table_key(value: str) -> str:
    token = str(value or "").strip().lower().split(":")[-1]
    token = re.sub(r"^table[-_]", "", token)
    return re.sub(r"-block-\d+$", "", token)


def _binding_distance(
    item: dict[str, Any] | None,
    candidate: dict[str, Any],
) -> int:
    scope = dimension_binding_scope(item, candidate)
    return {
        "table": 0,
        "table_group": 1,
        "page": 2,
        "source": 3,
    }.get(scope, 4)


def _same_field(
    left: dict[str, Any],
    right: dict[str, Any],
    field: str,
) -> bool:
    left_value = _item_dimension(left, field)
    right_value = _item_dimension(right, field)
    return bool(left_value and left_value == right_value)


def _item_id(item: dict[str, Any] | None) -> str:
    if item is None:
        return ""
    return str(
        item.get("evidence_id")
        or item.get("element_id")
        or item.get("canonical_id")
        or ""
    ).strip()


def _source_id(item: dict[str, Any] | None) -> str:
    if item is None:
        return ""
    return source_identity(item)


def _item_text(item: dict[str, Any] | None) -> str:
    if item is None:
        return ""
    return " ".join(
        str(item.get(field) or "")
        for field in ("text", "ocr_text", "vlm_text", "caption")
    )


def _item_dimension(item: dict[str, Any] | None, field: str) -> str:
    if item is None:
        return ""
    metadata = dict(item.get("metadata") or {})
    return str(item.get(field) or metadata.get(field) or "").strip()


def _is_atomic_evidence(item: dict[str, Any]) -> bool:
    return str(item.get("evidence_level") or "").strip().lower() in {"cell", "span"}
