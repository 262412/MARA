from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any

from .evidence_alias_values import exact_alias_values, grouping_alias_values
from .evidence_fact_contract import (
    STRUCTURED_FACT_FIELDS,
    EvidenceIdentityConflictError,
    fact_sets_conflict,
    polarity,
)
from .evidence_field_values import score_value
from .evidence_representations import (
    dict_list,
    evidence_representations,
    stable_dict_union,
)
from .evidence_similarity import cosine_item_similarity, minhash_text_similarity

EVIDENCE_BUNDLE_SCHEMA_VERSION = "evidence_bundle.v2"
OVERLAP_THRESHOLD = 0.75
MINHASH_THRESHOLD = 0.90
SEMANTIC_THRESHOLD = 0.94

_TOKEN_RE = re.compile(r"[\w.%$€£¥-]+", re.UNICODE)
_NUMBER_RE = re.compile(r"(?<!\w)[+-]?(?:\d[\d,]*)(?:\.\d+)?%?")
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_UNIT_RE = re.compile(
    r"\b(?:percent|percentage|million|billion|thousand|usd|eur|gbp|ratio)\b|[%$€£¥]",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class EvidenceIdentity:
    source_id: str
    kind: str
    local_id: str

    @property
    def key(self) -> str:
        return ":".join(
            _identity_component(value)
            for value in (self.kind, self.source_id, self.local_id)
        )

    @property
    def legacy_key(self) -> str:
        return ":".join((self.kind, self.source_id, self.local_id))

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def evidence_aliases(item: dict[str, Any]) -> set[str]:
    return exact_evidence_aliases(item) | grouping_evidence_aliases(item)


def exact_evidence_aliases(item: dict[str, Any]) -> set[str]:
    identity = identity_of(item)
    aliases = exact_alias_values(
        item,
        identity_key=identity.key,
        identity_kind=identity.kind,
    )
    if identity.legacy_key != identity.key:
        aliases.add(identity.legacy_key)
    return aliases


def grouping_evidence_aliases(item: dict[str, Any]) -> set[str]:
    return grouping_alias_values(
        item,
        exact_aliases=exact_evidence_aliases(item),
    )


def identity_of(item: dict[str, Any]) -> EvidenceIdentity:
    metadata = _merged_metadata(item)
    source_id = _first(
        item,
        metadata,
        "source_id",
        "file_id",
        "document_id",
        "runtime_source_id",
    )
    cell_id = _first(item, metadata, "cell_id")
    if cell_id:
        return EvidenceIdentity(source_id, "cell", cell_id)

    span_id = _first(item, metadata, "span_id")
    if span_id:
        return EvidenceIdentity(source_id, "span", span_id)
    evidence_level = _first(item, metadata, "evidence_level").lower()

    table_id = _first(item, metadata, "table_id")
    row_index = _optional_int(_value(item, metadata, "row_index", "row"))
    column_index = _optional_int(
        _value(item, metadata, "column_index", "column", "col")
    )
    if table_id and row_index is not None and column_index is not None:
        period_kind = _first(item, metadata, "period_kind")
        local_id = f"{table_id}:{period_kind}:{row_index}:{column_index}"
        return EvidenceIdentity(source_id, "cell", local_id)

    element_id = _first(item, metadata, "element_id")
    if evidence_level == "span" and element_id:
        return EvidenceIdentity(source_id, "span", element_id)
    if element_id:
        return EvidenceIdentity(source_id, "element", element_id)
    return _fallback_identity(item, metadata, source_id, evidence_level)


def _fallback_identity(
    item: dict[str, Any],
    metadata: dict[str, Any],
    source_id: str,
    evidence_level: str,
) -> EvidenceIdentity:
    evidence_id = _first(item, metadata, "evidence_id", "doc_id")
    if (
        evidence_level in {"page", "source"}
        and not evidence_id
        and not _item_text(item)
    ):
        page_label = _first(
            item,
            metadata,
            "page_label",
            "page_number",
            "page",
            "page_idx",
        )
        return EvidenceIdentity(
            source_id,
            evidence_level,
            page_label if evidence_level == "page" else "source",
        )

    page_label = _first(
        item,
        metadata,
        "page_label",
        "page_number",
        "page",
        "page_idx",
    )
    bbox = _quantized_bbox(item.get("bbox", metadata.get("bbox")))
    if page_label and bbox:
        return EvidenceIdentity(source_id, "element", f"{page_label}:{bbox}")

    chunk_start = _optional_int(
        _value(item, metadata, "chunk_start", "start_char", "start")
    )
    chunk_end = _optional_int(_value(item, metadata, "chunk_end", "end_char", "end"))
    if page_label and chunk_start is not None and chunk_end is not None:
        return EvidenceIdentity(
            source_id,
            "chunk",
            f"{page_label}:{chunk_start}:{chunk_end}",
        )

    if evidence_id:
        return EvidenceIdentity(source_id, "evidence", evidence_id)

    text_hash = str(item.get("normalized_text_hash") or "").strip()
    if not text_hash:
        text_hash = _normalized_text_hash(_item_text(item))
    local_id = ":".join(value for value in (page_label, text_hash) if value)
    if local_id:
        return EvidenceIdentity(source_id, "text", local_id)
    raise ValueError("Evidence record has no stable identity fields.")


def canonicalize_and_dedupe_evidence(
    items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    trace: dict[str, Any] = {
        "schema_version": EVIDENCE_BUNDLE_SCHEMA_VERSION,
        "input_count": len(items),
        "output_count": 0,
        "structure_duplicate_count": 0,
        "exact_text_duplicate_count": 0,
        "overlap_duplicate_count": 0,
        "minhash_duplicate_count": 0,
        "semantic_duplicate_count": 0,
        "conflict_guard_count": 0,
    }
    for raw_item in items:
        item = canonicalize_evidence_item(raw_item)
        duplicate, reason, conflicts = _find_duplicate(item, selected)
        trace["conflict_guard_count"] += conflicts
        if duplicate is None:
            selected.append(item)
            continue
        _merge_duplicate(duplicate, item)
        trace[f"{reason}_duplicate_count"] += 1
    trace["output_count"] = len(selected)
    trace["duplicate_ratio"] = round(
        (len(items) - len(selected)) / len(items) if items else 0.0,
        4,
    )
    return selected, trace


def canonicalize_evidence_item(item: dict[str, Any]) -> dict[str, Any]:
    output = dict(item)
    expected_identity = item.get("identity")
    output.pop("identity", None)
    metadata = _merged_metadata(item)
    source_id = _first(
        item,
        metadata,
        "source_id",
        "file_id",
        "document_id",
        "runtime_source_id",
    )
    page_label = _first(item, metadata, "page_label", "page_number", "page", "page_idx")
    element_id = _first(item, metadata, "element_id")
    parent_id = _first(item, metadata, "parent_element_id", "parent_id")
    text = _item_text(item)
    normalized_hash = _normalized_text_hash(text)
    fields = {
        "source_id": source_id,
        "page_label": page_label,
        "element_id": element_id,
        "cell_id": _first(item, metadata, "cell_id"),
        "span_id": _first(item, metadata, "span_id"),
        "parent_element_id": parent_id,
        "neighbor_element_ids": _string_list(
            item.get("neighbor_element_ids")
            or metadata.get("neighbor_element_ids")
            or metadata.get("neighbors")
        ),
        "section_id": _first(item, metadata, "section_id"),
        "table_id": _first(item, metadata, "table_id"),
        "row_index": _optional_int(_value(item, metadata, "row_index", "row")),
        "column_index": _optional_int(
            _value(item, metadata, "column_index", "column", "col")
        ),
        "continuation_id": _first(
            item, metadata, "continuation_id", "table_continuation_id"
        ),
        "chunk_start": _optional_int(
            _value(item, metadata, "chunk_start", "start_char", "start")
        ),
        "chunk_end": _optional_int(
            _value(item, metadata, "chunk_end", "end_char", "end")
        ),
        "normalized_text_hash": normalized_hash,
        **{
            field: _value(item, metadata, field)
            for field in STRUCTURED_FACT_FIELDS
            if field not in {"cell_id", "table_id", "row_index", "column_index"}
        },
    }
    output.update(fields)
    output["bbox"] = item.get("bbox", metadata.get("bbox"))
    output["source_backrefs"] = _source_backrefs(output)
    output["duplicate_evidence_ids"] = _string_list(item.get("duplicate_evidence_ids"))
    output["retrieval_lineage"] = dict_list(
        item.get("retrieval_lineage") or metadata.get("retrieval_lineage")
    )
    output["representations"] = evidence_representations(item)
    output["metadata"] = metadata
    identity = identity_of(output)
    if isinstance(expected_identity, dict):
        expected = EvidenceIdentity(
            str(expected_identity.get("source_id") or "").strip(),
            str(expected_identity.get("kind") or "").strip(),
            str(expected_identity.get("local_id") or "").strip(),
        )
        if expected.kind and expected.local_id and expected != identity:
            raise EvidenceIdentityConflictError(
                f"Embedded identity {expected.key!r} does not match "
                f"recomputed identity {identity.key!r}."
            )
    output["identity"] = identity.as_dict()
    output["canonical_id"] = identity.key
    return output


def _find_duplicate(
    item: dict[str, Any], selected: list[dict[str, Any]]
) -> tuple[dict[str, Any] | None, str, int]:
    conflicts = 0
    item_structure = _structure_key(item)
    for existing in selected:
        if item_structure and item_structure == _structure_key(existing):
            return existing, "structure", conflicts
    text_hash = str(item.get("normalized_text_hash") or "")
    for existing in selected:
        if (
            text_hash
            and text_hash == existing.get("normalized_text_hash")
            and _text_dedupe_allowed(item, existing)
        ):
            if _facts_conflict(item, existing):
                conflicts += 1
                continue
            return existing, "exact_text", conflicts
    for existing in selected:
        if _overlapping_chunks(item, existing):
            if _facts_conflict(item, existing):
                conflicts += 1
                continue
            return existing, "overlap", conflicts
    for existing in selected:
        if (
            _near_duplicate_allowed(item, existing)
            and minhash_text_similarity(_item_text(item), _item_text(existing))
            >= MINHASH_THRESHOLD
        ):
            if _facts_conflict(item, existing):
                conflicts += 1
                continue
            return existing, "minhash", conflicts
    for existing in selected:
        if not _near_duplicate_allowed(item, existing):
            continue
        if cosine_item_similarity(item, existing) < SEMANTIC_THRESHOLD:
            continue
        if _facts_conflict(item, existing):
            conflicts += 1
            continue
        return existing, "semantic", conflicts
    return None, "", conflicts


def _structure_key(item: dict[str, Any]) -> tuple[Any, ...] | None:
    try:
        identity = identity_of(item)
    except ValueError:
        return None
    return (identity.kind, identity.source_id, identity.local_id)


def _merge_duplicate(target: dict[str, Any], duplicate: dict[str, Any]) -> None:
    _assert_same_structured_fact(target, duplicate)
    duplicate_id = str(duplicate.get("evidence_id") or "")
    ids = list(target.get("duplicate_evidence_ids") or [])
    ids.extend(duplicate.get("duplicate_evidence_ids") or [])
    if duplicate_id and duplicate_id != target.get("evidence_id"):
        ids.append(duplicate_id)
    target["duplicate_evidence_ids"] = _unique(ids)
    target["source_backrefs"] = _unique(
        list(target.get("source_backrefs") or [])
        + list(duplicate.get("source_backrefs") or [])
    )
    target["retrieval_lineage"] = stable_dict_union(
        target.get("retrieval_lineage"),
        duplicate.get("retrieval_lineage"),
    )
    target["representations"] = stable_dict_union(
        target.get("representations"),
        duplicate.get("representations"),
    )
    metadata = dict(target.get("metadata") or {})
    duplicate_metadata = dict(duplicate.get("metadata") or {})
    metadata["dedupe_source_ids"] = _unique(
        list(metadata.get("dedupe_source_ids") or [])
        + list(duplicate_metadata.get("dedupe_source_ids") or [])
        + [
            source_id
            for source_id in (
                str(target.get("source_id") or ""),
                str(duplicate.get("source_id") or ""),
            )
            if source_id
        ]
    )
    metadata["dedupe_members"] = _unique(
        list(metadata.get("dedupe_members") or [])
        + [
            value
            for value in (
                str(target.get("evidence_id") or ""),
                duplicate_id,
            )
            if value
        ]
    )
    for key, value in duplicate_metadata.items():
        if key not in metadata:
            metadata[key] = value
        elif _is_score_key(key):
            metadata[key] = max(score_value(metadata[key]), score_value(value))
    target["metadata"] = metadata


def _assert_same_structured_fact(
    target: dict[str, Any],
    duplicate: dict[str, Any],
) -> None:
    if identity_of(target) != identity_of(duplicate):
        return
    conflicts = [
        field
        for field in STRUCTURED_FACT_FIELDS
        if target.get(field) not in (None, "")
        and duplicate.get(field) not in (None, "")
        and str(target.get(field)) != str(duplicate.get(field))
    ]
    if conflicts:
        raise EvidenceIdentityConflictError(
            "Conflicting structured fields for evidence identity "
            f"{identity_of(target).key}: {', '.join(conflicts)}"
        )
    if _facts_conflict(target, duplicate):
        raise EvidenceIdentityConflictError(
            "Conflicting textual facts for evidence identity "
            f"{identity_of(target).key}."
        )


def _text_dedupe_allowed(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_identity = identity_of(left)
    right_identity = identity_of(right)
    if left_identity.kind in {"cell", "span"} or right_identity.kind in {
        "cell",
        "span",
    }:
        return left_identity == right_identity
    if left_identity.source_id != right_identity.source_id:
        return False
    if str(left.get("page_label") or "") != str(right.get("page_label") or ""):
        return False
    return str(left.get("modality") or "") == str(right.get("modality") or "")


def _near_duplicate_allowed(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if not _text_dedupe_allowed(left, right):
        return False
    left_parent = str(left.get("parent_element_id") or "")
    right_parent = str(right.get("parent_element_id") or "")
    return not (left_parent or right_parent) or left_parent == right_parent


def _overlapping_chunks(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if not _same_structure_context(left, right):
        return False
    left_start = _optional_int(left.get("chunk_start"))
    right_start = _optional_int(right.get("chunk_start"))
    left_end = _optional_int(left.get("chunk_end"))
    right_end = _optional_int(right.get("chunk_end"))
    if None in (left_start, right_start, left_end, right_end):
        return False
    assert left_start is not None and right_start is not None
    assert left_end is not None and right_end is not None
    left_length = max(1, left_end - left_start)
    right_length = max(1, right_end - right_start)
    intersection = max(
        0,
        min(left_end, right_end) - max(left_start, right_start),
    )
    return intersection / min(left_length, right_length) >= OVERLAP_THRESHOLD


def _same_structure_context(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return all(
        str(left.get(field) or "") == str(right.get(field) or "")
        for field in ("source_id", "page_label", "parent_element_id")
    ) and bool(left.get("source_id") or left.get("parent_element_id"))


def _facts_conflict(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_text = _item_text(left)
    right_text = _item_text(right)
    for extractor in (_numbers, _years, _units):
        a = extractor(left_text)
        b = extractor(right_text)
        if fact_sets_conflict(
            identity_of(left).kind,
            identity_of(right).kind,
            a,
            b,
        ):
            return True
    left_polarity = polarity(_tokens(left_text))
    right_polarity = polarity(_tokens(right_text))
    return bool(left_polarity and right_polarity and left_polarity != right_polarity)


def _numbers(text: str) -> set[str]:
    return {value.replace(",", "") for value in _NUMBER_RE.findall(text)}


def _years(text: str) -> set[str]:
    return set(_YEAR_RE.findall(text))


def _units(text: str) -> set[str]:
    return {value.lower() for value in _UNIT_RE.findall(text)}


def _normalized_text_hash(text: str) -> str:
    normalized = " ".join(
        unicodedata.normalize("NFKC", str(text or "")).lower().split()
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest() if normalized else ""


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(str(text or ""))}


def _item_text(item: dict[str, Any]) -> str:
    direct = [
        str(item.get(field) or "").strip()
        for field in ("text", "ocr_text", "vlm_text", "caption")
        if str(item.get(field) or "").strip()
    ]
    represented = [
        str(value.get("text") or "").strip()
        for value in evidence_representations(item)
        if str(value.get("text") or "").strip()
    ]
    return "\n".join(dict.fromkeys([*direct, *represented]))


def _merged_metadata(item: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(item.get("metadata") or {})
    nested = metadata.pop("metadata", None)
    return {**dict(nested or {}), **metadata} if isinstance(nested, dict) else metadata


def _value(item: dict[str, Any], metadata: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if item.get(key) is not None:
            return item[key]
        if metadata.get(key) is not None:
            return metadata[key]
    return None


def _first(item: dict[str, Any], metadata: dict[str, Any], *keys: str) -> str:
    value = _value(item, metadata, *keys)
    return str(value).strip() if value is not None else ""


def _source_backrefs(item: dict[str, Any]) -> list[str]:
    refs = _string_list(item.get("source_backrefs"))
    source = str(item.get("source_id") or "")
    page = str(item.get("page_label") or "")
    if not refs and source:
        refs.append(f"{source}#page:{page}" if page else f"{source}#source")
    return _unique(refs)


def _string_list(value: Any) -> list[str]:
    if isinstance(value, dict):
        values: list[Any] = list(value.values())
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    elif value is None:
        return []
    else:
        values = [value]
    return _unique([str(item).strip() for item in values if str(item).strip()])


def _optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _quantized_bbox(value: Any) -> tuple[float, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    try:
        return tuple(round(float(item), 1) for item in value)
    except (TypeError, ValueError):
        return ()


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _is_score_key(key: str) -> bool:
    return str(key).endswith("_score") or str(key) in {"score", "confidence"}


def _identity_component(value: str) -> str:
    return str(value).replace("%", "%25").replace(":", "%3A")
