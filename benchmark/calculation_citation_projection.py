from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ktem.docqa.calculation_evidence_identity import materialize_financial_cell
from ktem.docqa.evidence_identity import exact_evidence_aliases, identity_of
from ktem.docqa.financial_table import parse_financial_table_cells


@dataclass(frozen=True)
class MatchedCitationEvidence:
    citation_identity: str
    item: dict[str, Any]


def calculation_citation_items(
    prediction: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> list[MatchedCitationEvidence]:
    citation_ids = _calculation_citation_ids(prediction)
    if not citation_ids:
        return []
    matched: list[MatchedCitationEvidence] = []
    for citation_id in citation_ids:
        for item in candidates:
            matched_item = _matched_calculation_item(citation_id, item)
            if matched_item is not None:
                matched.append(
                    MatchedCitationEvidence(
                        citation_identity=citation_id,
                        item=matched_item,
                    )
                )
                break
    return matched


def record_calculation_stage_evidence(
    prediction: dict[str, Any],
    matches: list[MatchedCitationEvidence],
    *,
    canonical_sources: list[str] | None = None,
) -> None:
    metadata = prediction.get("evidence_metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        prediction["evidence_metadata"] = metadata
    metadata["execution_operand_evidence"] = [
        _with_canonical_source_backref(match.item, canonical_sources or [])
        for match in matches
    ]


def _with_canonical_source_backref(
    item: dict[str, Any],
    canonical_sources: list[str],
) -> dict[str, Any]:
    page = str(item.get("page_label") or item.get("page") or "").strip()
    from .citation_rendering import matching_canonical_source_ref

    source_ref = matching_canonical_source_ref(
        canonical_sources,
        page,
        source_id=str(
            item.get("source_id")
            or item.get("file_id")
            or item.get("runtime_source_id")
            or ""
        ).strip(),
        source_aliases=tuple(item.get("source_aliases") or ()),
    )
    if not source_ref:
        return item
    output = dict(item)
    output["source_backrefs"] = list(
        dict.fromkeys([*list(item.get("source_backrefs") or []), source_ref])
    )
    return output


def _matched_calculation_item(
    citation_id: str,
    item: dict[str, Any],
) -> dict[str, Any] | None:
    if citation_id in exact_evidence_aliases(item):
        return item
    for cell in parse_financial_table_cells(item):
        cell_item = materialize_financial_cell(item, cell)
        identity = identity_of(cell_item).key
        if citation_id == identity:
            return cell_item
    return None


def _calculation_citation_ids(prediction: dict[str, Any]) -> list[str]:
    evidence_bundle = prediction.get("evidence_bundle")
    bundle = evidence_bundle if isinstance(evidence_bundle, dict) else {}
    evidence_metadata = prediction.get("evidence_metadata")
    metadata = evidence_metadata if isinstance(evidence_metadata, dict) else {}
    trace_containers = [
        metadata,
        dict(bundle.get("metadata") or {}),
        bundle,
    ]
    for container in trace_containers:
        trace = dict(container.get("finance_numeric_trace") or {})
        execution = dict(trace.get("calculation_execution") or {})
        if execution.get("status") != "ok":
            continue
        return list(
            dict.fromkeys(
                str(citation_id).strip()
                for citation_id in execution.get("citation_ids") or []
                if str(citation_id or "").strip()
            )
        )
    return []
