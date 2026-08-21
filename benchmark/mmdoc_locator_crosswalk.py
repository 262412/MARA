from __future__ import annotations

import re
from typing import Any

from ktem.docqa.evidence_identity import identity_of

MMDOC_LOCATOR_CROSSWALK_CONTRACT = "mmdoc_locator_crosswalk.v1"

_YEAR_VALUE_RE = re.compile(
    r"(?P<period>(?:19|20)\d{2})(?:/\d+)?\s*(?:[:=]\s*)?"
    r"(?P<value>[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)"
)
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_METRIC_STOPWORDS = {
    "and",
    "for",
    "from",
    "fiscal",
    "over",
    "returns",
    "the",
    "years",
}


def audited_mmdoc_page_hit(prediction: dict[str, Any]) -> float | None:
    """Score an MMDoc runtime page only through an audited locator crosswalk.

    This is deliberately separate from generic page alignment: a runtime page
    is equivalent to a gold page only when the crosswalk has already matched
    every required period/value pair and metric anchor.  No page-distance or
    neighbouring-page inference is performed here.
    """

    coverage = audited_mmdoc_page_coverage(prediction)
    return None if coverage is None else float(coverage > 0.0)


def audited_mmdoc_page_coverage(prediction: dict[str, Any]) -> float | None:
    """Measure gold-locator coverage through exact audited MMDoc mappings."""

    crosswalk = _crosswalk_from_prediction(prediction)
    if not isinstance(crosswalk, dict) or not _is_audited_crosswalk(crosswalk):
        return None
    predicted_pages = {
        str(page).strip()
        for page in prediction.get("predicted_pages") or []
        if str(page).strip()
    }
    gold_records = [
        item for item in _records(prediction.get("gold_evidence")) if _page(item)
    ]
    if not gold_records or not predicted_pages:
        return 0.0
    mappings = _records(crosswalk.get("mappings"))
    hits = sum(
        any(
            _mapping_matches_gold(mapping, gold)
            and not predicted_pages.isdisjoint(_mapping_runtime_pages(mapping))
            for mapping in mappings
        )
        for gold in gold_records
    )
    return hits / len(gold_records)


def _crosswalk_from_prediction(prediction: dict[str, Any]) -> dict[str, Any] | None:
    metadata = prediction.get("evidence_metadata")
    crosswalk = prediction.get("mmdoc_locator_crosswalk")
    if not isinstance(crosswalk, dict) and isinstance(metadata, dict):
        crosswalk = metadata.get("mmdoc_locator_crosswalk")
    return crosswalk if isinstance(crosswalk, dict) else None


def _mapping_matches_gold(mapping: dict[str, Any], expected: dict[str, Any]) -> bool:
    gold = mapping.get("gold")
    if not isinstance(gold, dict):
        return False
    return all(
        (
            str(gold.get("source_id") or "").strip().lower() in _source_ids(expected),
            str(gold.get("page") or "").strip() == _page(expected),
            str(gold.get("element_id") or "").strip().lower()
            == str(expected.get("element_id") or "").strip().lower(),
            _element_type_compatible(_element_type(expected), _element_type(gold)),
        )
    )


def _mapping_identity_ids(mapping: dict[str, Any]) -> set[str]:
    runtime = mapping.get("runtime")
    return (
        {
            str(identity).strip()
            for key in ("evidence_ids", "canonical_ids")
            for identity in _list_values(runtime.get(key))
            if str(identity).strip()
        }
        if isinstance(runtime, dict)
        else set()
    )


def _mapping_runtime_pages(mapping: dict[str, Any]) -> set[str]:
    runtime = mapping.get("runtime")
    if not isinstance(runtime, dict):
        return set()
    return {
        str(page).strip()
        for page in _list_values(runtime.get("page_labels"))
        if str(page).strip()
    }


def _evidence_canonical_ids(item: dict[str, Any]) -> set[str]:
    return {value for value in (_evidence_id(item), _canonical_id(item)) if value}


def _is_audited_crosswalk(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and value.get("contract_id") == MMDOC_LOCATOR_CROSSWALK_CONTRACT
        and value.get("status") == "audited_exact_match"
        and value.get("basis") == "exact_period_value_and_metric_anchors"
    )


def apply_mmdoc_locator_crosswalk(
    prediction: dict[str, Any],
    *,
    dataset_name: str | None = None,
) -> dict[str, Any]:
    """Project an audited MMDoc gold locator onto verified runtime cells.

    The mapping is accepted only when source identity, metric anchors, and every
    period/value pair in the gold quote agree with the typed runtime cells.  Page
    differences are recorded as locator aliases after that content check; they
    are never used as a page-offset heuristic.
    """

    if not _is_mmdoc_prediction(prediction, dataset_name):
        return _not_applicable("dataset_not_mmdoc")
    metadata = prediction.get("evidence_metadata")
    if not isinstance(metadata, dict):
        return _not_applicable("missing_evidence_metadata")
    projection = metadata.get("final_binding_projection")
    if not isinstance(projection, dict) or not _is_verified_projection(projection):
        return _not_applicable("missing_final_binding_projection")
    runtime_items = _runtime_items_for_projection(prediction, projection, metadata)
    if not runtime_items:
        return _not_applicable("missing_projected_runtime_cells")
    mappings: list[dict[str, Any]] = []
    for gold in _records(prediction.get("gold_evidence")):
        mapping = _audit_gold_locator(gold, runtime_items)
        if mapping is None:
            continue
        mappings.append(mapping)
    if not mappings:
        return _not_applicable("no_exact_visual_fact_match")
    crosswalk = {
        "contract_id": MMDOC_LOCATOR_CROSSWALK_CONTRACT,
        "status": "audited_exact_match",
        "basis": "exact_period_value_and_metric_anchors",
        "mappings": mappings,
    }
    metadata["mmdoc_locator_crosswalk"] = crosswalk
    _project_record_aliases(prediction, metadata, mappings)
    evidence_bundle = prediction.get("evidence_bundle")
    if isinstance(evidence_bundle, dict):
        bundle_metadata = evidence_bundle.get("metadata")
        if isinstance(bundle_metadata, dict):
            bundle_metadata["mmdoc_locator_crosswalk"] = crosswalk
    prediction["mmdoc_locator_crosswalk"] = crosswalk
    return crosswalk


def _is_verified_projection(projection: dict[str, Any]) -> bool:
    try:
        coverage = float(str(projection.get("verified_slot_coverage")))
    except (TypeError, ValueError):
        return False
    return bool(
        projection.get("contract_id") == "visual_final_binding_projection.v1"
        and projection.get("status") == "verified_support"
        and coverage == 1.0
    )


def _is_mmdoc_prediction(
    prediction: dict[str, Any],
    dataset_name: str | None,
) -> bool:
    values = (
        dataset_name,
        prediction.get("dataset_name"),
        prediction.get("dataset_family"),
        prediction.get("verification_domain"),
    )
    return any("mmdoc" in str(value or "").strip().lower() for value in values)


def _runtime_items_for_projection(
    prediction: dict[str, Any],
    projection: dict[str, Any],
    metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    requested_ids = {
        str(evidence_id).strip()
        for values in (projection.get("slot_bindings") or {}).values()
        for evidence_id in values or []
        if str(evidence_id).strip()
    }
    if not requested_ids:
        return []
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    values: list[Any] = []
    for key in (
        "verified_evidence",
        "verified_claim_support_evidence",
        "cited_evidence",
        "emitted_citation_evidence",
    ):
        values.append(metadata.get(key))
    values.append(prediction.get("retrieved_hits"))
    evidence_bundle = prediction.get("evidence_bundle")
    if isinstance(evidence_bundle, dict):
        values.append(evidence_bundle.get("items"))
    for value in values:
        for item in _records(value):
            identities = _record_identities(item)
            matched = identities & requested_ids
            if not matched:
                continue
            marker = min(matched)
            if marker in seen:
                continue
            seen.add(marker)
            records.append(item)
    return records


def _audit_gold_locator(
    gold: dict[str, Any], runtime_items: list[dict[str, Any]]
) -> dict[str, Any] | None:
    source_ids = _source_ids(gold)
    source_label = _source_label(gold)
    gold_page = _page(gold)
    gold_element_id = str(gold.get("element_id") or "").strip()
    gold_element_type = _element_type(gold)
    quote = str(
        gold.get("image_quote") or gold.get("quote") or gold.get("text") or ""
    ).strip()
    period_values = _period_values(quote)
    if not source_ids or not gold_page or not gold_element_id or not period_values:
        return None
    anchor_match: tuple[
        dict[str, str], set[str], dict[str, dict[str, Any]]
    ] | None = None
    for section in _quote_sections(quote):
        section_period_values = _period_values(section)
        if not section_period_values:
            continue
        metric_tokens = _metric_tokens(section)
        matched_items = [
            item
            for item in runtime_items
            if _source_ids(item) & source_ids
            and _element_type_compatible(_element_type(item), gold_element_type)
            and _metric_matches(item, metric_tokens)
            and _item_period_value(item) in section_period_values.items()
        ]
        by_period = {
            next(iter(_period_values_for_item(item))): item for item in matched_items
        }
        if set(by_period) == set(section_period_values):
            anchor_match = (section_period_values, metric_tokens, by_period)
            break
    if anchor_match is None:
        return None
    period_values, metric_tokens, by_period = anchor_match
    ordered_items = [by_period[period] for period in period_values]
    runtime_pages = _unique(_page(item) for item in ordered_items)
    runtime_element_ids = _unique(
        str(item.get("element_id") or "").strip() for item in ordered_items
    )
    runtime_cell_ids = _unique(
        str(item.get("cell_id") or "").strip() for item in ordered_items
    )
    runtime_canonical_ids = _unique(_canonical_id(item) for item in ordered_items)
    evidence_ids = _unique(_evidence_id(item) for item in ordered_items)
    if not evidence_ids:
        return None
    return {
        "gold": {
            "source_id": source_label,
            "page": gold_page,
            "element_id": gold_element_id,
            "element_type": gold_element_type,
        },
        "runtime": {
            "evidence_ids": evidence_ids,
            "canonical_ids": runtime_canonical_ids,
            "page_labels": runtime_pages,
            "element_ids": runtime_element_ids,
            "cell_ids": runtime_cell_ids,
        },
        "anchors": {
            "period_value_pairs": [
                {"period": period, "value": period_values[period]}
                for period in period_values
            ],
            "metric_tokens": sorted(metric_tokens),
        },
    }


def _project_record_aliases(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
    mappings: list[dict[str, Any]],
) -> None:
    aliases_by_evidence_id: dict[str, tuple[str, str]] = {}
    for mapping in mappings:
        gold = mapping["gold"]
        alias = (str(gold["page"]), str(gold["element_id"]))
        for evidence_id in mapping["runtime"]["evidence_ids"]:
            aliases_by_evidence_id[str(evidence_id)] = alias
        for canonical_id in mapping["runtime"]["canonical_ids"]:
            aliases_by_evidence_id[str(canonical_id)] = alias
    for key in (
        "verified_evidence",
        "verified_claim_support_evidence",
        "cited_evidence",
        "emitted_citation_evidence",
    ):
        if key in metadata:
            metadata[key] = _records_with_aliases(metadata[key], aliases_by_evidence_id)
    if "retrieved_hits" in prediction:
        prediction["retrieved_hits"] = _records_with_aliases(
            prediction.get("retrieved_hits"), aliases_by_evidence_id
        )
    evidence_bundle = prediction.get("evidence_bundle")
    if isinstance(evidence_bundle, dict) and "items" in evidence_bundle:
        evidence_bundle["items"] = _records_with_aliases(
            evidence_bundle.get("items"), aliases_by_evidence_id
        )


def _records_with_aliases(
    value: Any,
    aliases_by_evidence_id: dict[str, tuple[str, str]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for item in _records(value):
        evidence_ids = _record_identities(item)
        aliases = [
            aliases_by_evidence_id[evidence_id]
            for evidence_id in evidence_ids
            if evidence_id in aliases_by_evidence_id
        ]
        if not aliases:
            output.append(item)
            continue
        page_aliases = _unique(
            [*_list_values(item.get("page_aliases")), *(page for page, _ in aliases)]
        )
        element_aliases = _unique(
            [
                *_list_values(item.get("element_id_aliases")),
                *(element_id for _, element_id in aliases),
            ]
        )
        updated = dict(item)
        updated["page_aliases"] = page_aliases
        updated["element_id_aliases"] = element_aliases
        output.append(updated)
    return output


def _period_values(value: str) -> dict[str, str]:
    output: dict[str, str] = {}
    for match in _YEAR_VALUE_RE.finditer(value):
        period = match.group("period")
        number = _normalize_number(match.group("value"))
        if period not in output:
            output[period] = number
    return output


def _period_values_for_item(item: dict[str, Any]) -> dict[str, str]:
    period = str(item.get("period") or item.get("column_label") or "").strip()
    value = str(item.get("value") or "").strip()
    if period and value and re.fullmatch(r"(?:19|20)\d{2}", period):
        return {period: _normalize_number(value)}
    return _period_values(
        " ".join(str(item.get(key) or "") for key in ("text", "ocr_text", "vlm_text"))
    )


def _item_period_value(item: dict[str, Any]) -> tuple[str, str] | None:
    values = _period_values_for_item(item)
    if len(values) != 1:
        return None
    return next(iter(values.items()))


def _metric_tokens(value: str) -> set[str]:
    headings = re.findall(r"\*\*([^*]+)\*\*", value)
    if headings:
        prefix = headings[0].split("(", 1)[0]
    else:
        first_year = re.search(r"(?:19|20)\d{2}", value)
        prefix = value[: first_year.start()] if first_year else value
    return {
        token
        for token in _TOKEN_RE.findall(prefix.lower())
        if len(token) >= 3 and token not in _METRIC_STOPWORDS
    }


def _metric_matches(item: dict[str, Any], metric_tokens: set[str]) -> bool:
    if not metric_tokens:
        return False
    text = " ".join(
        str(item.get(key) or "")
        for key in ("row_label", "column_label", "table_label", "text", "ocr_text")
    ).lower()
    return metric_tokens <= set(_TOKEN_RE.findall(text))


def _source_ids(item: dict[str, Any]) -> set[str]:
    values = [
        item.get("evaluation_source_id"),
        item.get("document_id"),
        item.get("source_id"),
        item.get("runtime_source_id"),
        item.get("file_id"),
        item.get("file_name"),
        *_list_values(item.get("source_aliases")),
    ]
    for key in (
        "source_backrefs",
        "runtime_source_backrefs",
        "evaluation_source_backrefs",
    ):
        values.extend(
            str(value).split("#", 1)[0] for value in _list_values(item.get(key))
        )
    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        values.extend(
            [
                metadata.get("evaluation_source_id"),
                metadata.get("document_id"),
                metadata.get("source_id"),
                metadata.get("file_id"),
            ]
        )
    output: set[str] = set()
    for value in values:
        source = str(value or "").strip().lower()
        if "#" in source:
            source = source.split("#", 1)[0]
        source = source.rsplit("/", 1)[-1].removesuffix(".pdf")
        if source:
            output.add(source)
    return output


def _source_label(item: dict[str, Any]) -> str:
    values = (
        item.get("source_id"),
        item.get("document_id"),
        item.get("file_id"),
        item.get("file_name"),
    )
    for value in values:
        source = str(value or "").strip()
        if source:
            if "#" in source:
                source = source.split("#", 1)[0]
            return source.rsplit("/", 1)[-1].removesuffix(".pdf")
    return ""


def _quote_sections(quote: str) -> list[str]:
    sections = [
        section.strip()
        for section in re.split(r"(?=\n?\s*\d+\.\s+\*\*)", quote)
        if section.strip()
    ]
    return sections or [quote]


def _page(item: dict[str, Any]) -> str:
    return str(
        item.get("page_label") or item.get("page") or item.get("page_number") or ""
    ).strip()


def _element_type(item: dict[str, Any]) -> str:
    value = (
        str(item.get("element_type") or item.get("modality") or item.get("type") or "")
        .strip()
        .lower()
        .replace("-", "_")
    )
    return {"image": "figure", "fig": "figure", "chart": "figure"}.get(value, value)


def _element_type_compatible(runtime: str, gold: str) -> bool:
    if not gold or not runtime:
        return True
    return runtime == gold or {runtime, gold} <= {"table", "cell", "element"}


def _record_identities(item: dict[str, Any]) -> set[str]:
    identities = {
        str(item.get(key) or "").strip()
        for key in ("evidence_id", "cell_id", "span_id", "element_id")
        if str(item.get(key) or "").strip()
    }
    try:
        identity = identity_of(item).key
    except (TypeError, ValueError):
        identity = ""
    if identity:
        identities.add(identity)
    return identities


def _evidence_id(item: dict[str, Any]) -> str:
    value = str(item.get("evidence_id") or "").strip()
    if value:
        return value
    try:
        return identity_of(item).key
    except (TypeError, ValueError):
        return ""


def _canonical_id(item: dict[str, Any]) -> str:
    value = str(item.get("canonical_id") or "").strip()
    if value:
        return value
    try:
        return identity_of(item).key
    except (TypeError, ValueError):
        return ""


def _normalize_number(value: str) -> str:
    text = str(value or "").strip().replace(",", "")
    if text.startswith("+"):
        text = text[1:]
    return text


def _list_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [str(item) for item in value or [] if str(item).strip()]


def _unique(values: Any) -> list[str]:
    output: list[str] = []
    for value in values:
        value = str(value or "").strip()
        if value and value not in output:
            output.append(value)
    return output


def _records(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value or [] if isinstance(item, dict)]


def _not_applicable(reason: str) -> dict[str, Any]:
    return {
        "contract_id": MMDOC_LOCATOR_CROSSWALK_CONTRACT,
        "status": "not_applicable",
        "reason": reason,
        "mappings": [],
    }
