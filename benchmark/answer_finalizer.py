from __future__ import annotations

import json
import re
from typing import Any

from .answer_abstention import structured_or_text_abstention
from .answer_modes import normalize_benchmark_answer_mode
from .answer_repetition import deduplicate_final_answer as _deduplicate_final_answer
from .answer_scoring_adapter import select_scoring_answer
from .calculation_citation_projection import calculation_citation_items
from .citation_claim_selection import minimum_verified_claim_support_items
from .citation_rendering import citation_from_item as _citation_from_item
from .citation_rendering import citation_from_source_ref as _citation_from_source_ref
from .citation_rendering import (
    matching_canonical_source_ref as _matching_canonical_source_ref,
)
from .citation_stage_projection import (
    is_uuid_like_source_id,
    record_emitted_citation_evidence,
    source_ref_uses_uuid_like_source,
)
from .finance_answer_finalization import (
    enforce_finance_citation_authority,
    metadata_citations_allowed,
)
from .finance_citation_contract import (
    clear_answer_citation_state,
    record_execution_operand_evidence,
    record_verified_claim_support,
    typed_calculation_is_verified,
)
from .qasper_answer_normalization import is_unanswerable_text as _is_unanswerable_text
from .qasper_answer_normalization import (
    normalize_qasper_contract_answer as _normalize_qasper_contract_answer,
)
from .qasper_answer_normalization import (
    record_qasper_metadata as _record_qasper_metadata,
)
from .ragtruth_answer_contract import ragtruth_finalization_metadata

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_TRUNCATED_JSON_ANSWER_RE = re.compile(
    r'"answer"\s*:\s*"((?:\\.|[^"\\])*)"',
    re.DOTALL,
)


def finalize_prediction_answer(
    prediction: dict[str, Any],
    *,
    dataset_name: str,
    mode: str,
) -> None:
    normalized_mode = normalize_benchmark_answer_mode(mode)
    raw_answer = str(prediction.get("predicted_answer") or "")
    if "ragtruth" in str(dataset_name or "").strip().lower():
        _finalize_ragtruth_prediction(
            prediction,
            raw_answer=raw_answer,
            mode=normalized_mode,
        )
        return
    raw_answer, repetition_removed, repetition_kind = _deduplicate_final_answer(
        raw_answer,
        prediction=prediction,
        dataset_name=dataset_name,
    )
    raw_answer, qasper_contract_normalized = _normalize_qasper_contract_answer(
        raw_answer,
        prediction=prediction,
        dataset_name=dataset_name,
    )
    record_execution_operand_evidence(
        prediction,
        _citation_candidate_items(prediction),
        _canonical_source_refs(prediction),
    )
    enforce_finance_citation_authority(prediction, dataset_name=dataset_name)
    (
        answer_for_user,
        answer_text_for_user,
        answer_for_scoring_source,
        structured_answer,
        truncated_answer,
    ) = _prepare_standard_answer(
        raw_answer,
        prediction=prediction,
        dataset_name=dataset_name,
        mode=normalized_mode,
    )
    answer_for_scoring, source = select_scoring_answer(
        answer_for_user=answer_for_user,
        answer_for_scoring_source=answer_for_scoring_source,
        structured_answer=structured_answer,
        truncated_answer=truncated_answer,
        dataset_name=dataset_name,
        mode=normalized_mode,
    )
    if structured_or_text_abstention(prediction, answer_text_for_user):
        answer_for_scoring = "unanswerable"
        source = "canonical_abstention"
        prediction["answer_status"] = "abstained"
        answer_for_user = answer_text_for_user
        clear_answer_citation_state(prediction)
    else:
        prediction["answer_status"] = "answered"
    _store_finalized_answers(
        prediction,
        answer_for_user=answer_for_user,
        answer_for_scoring=answer_for_scoring,
        answer_text_for_user=answer_text_for_user,
        dataset_name=dataset_name,
        mode=normalized_mode,
        source=source,
        repetition_removed=repetition_removed,
        repetition_kind=repetition_kind,
    )
    _record_standard_finalization(
        prediction,
        raw_answer=raw_answer,
        answer_text_for_user=answer_text_for_user,
        dataset_name=dataset_name,
        qasper_contract_normalized=qasper_contract_normalized,
    )


def _record_standard_finalization(
    prediction: dict[str, Any],
    *,
    raw_answer: str,
    answer_text_for_user: str,
    dataset_name: str,
    qasper_contract_normalized: bool,
) -> None:
    _record_qasper_metadata(
        prediction, raw_answer, dataset_name, qasper_contract_normalized
    )
    record_emitted_citation_evidence(
        prediction,
        citations=_existing_structured_citations(
            prediction,
            span=answer_text_for_user,
        ),
        candidates=_citation_candidate_items(prediction),
    )


def _prepare_standard_answer(
    raw_answer: str,
    *,
    prediction: dict[str, Any],
    dataset_name: str,
    mode: str,
) -> tuple[str, str, str, dict[str, Any] | None, str]:
    structured_answer = _extract_structured_answer(raw_answer)
    truncated_answer = ""
    answer_for_scoring_source = raw_answer
    if structured_answer is not None:
        if prediction.get("finance_citation_authority_status"):
            structured_answer = {**structured_answer, "citations": []}
        answer_text_for_user = structured_answer["answer"]
        answer_for_user = _render_structured_answer_for_user(structured_answer)
        prediction["structured_citations"] = structured_answer["citations"]
        prediction["predicted_citations"] = _citation_texts(
            structured_answer["citations"]
        )
    else:
        truncated_answer = _extract_truncated_structured_answer(raw_answer)
        answer_for_user = truncated_answer or raw_answer
        answer_text_for_user = answer_for_user
        answer_for_scoring_source = answer_for_user
        if mode != "product" and metadata_citations_allowed(dataset_name, prediction):
            citations = attach_structured_citations_from_evidence(
                prediction,
                span=answer_for_user,
            )
            if citations:
                prediction["structured_citations"] = citations
                prediction["predicted_citations"] = _citation_texts(citations)
                answer_for_user = _render_structured_answer_for_user(
                    {"answer": answer_for_user, "citations": citations}
                )
    if mode != "product" and metadata_citations_allowed(dataset_name, prediction):
        citations = _canonicalized_existing_citations(
            prediction,
            span=answer_text_for_user,
        )
        if citations:
            prediction["structured_citations"] = citations
            prediction["predicted_citations"] = _citation_texts(citations)
            answer_for_user = _render_structured_answer_for_user(
                {"answer": answer_text_for_user, "citations": citations}
            )
    return (
        answer_for_user,
        answer_text_for_user,
        answer_for_scoring_source,
        structured_answer,
        truncated_answer,
    )


def _store_finalized_answers(
    prediction: dict[str, Any],
    *,
    answer_for_user: str,
    answer_for_scoring: str,
    answer_text_for_user: str,
    dataset_name: str,
    mode: str,
    source: str,
    repetition_removed: bool = False,
    repetition_kind: str = "",
) -> None:
    prediction["answer_for_user"] = answer_for_user
    prediction["answer_for_scoring"] = answer_for_scoring
    prediction["answer_finalization"] = {
        "mode": mode,
        "source": source,
        "repetition_removed": repetition_removed,
        "repetition_kind": repetition_kind,
    }
    if "ragtruth" in str(dataset_name or "").lower():
        prediction["answer_finalization"].update(
            ragtruth_finalization_metadata(answer_text_for_user)
        )


def _finalize_ragtruth_prediction(
    prediction: dict[str, Any],
    *,
    raw_answer: str,
    mode: str,
) -> None:
    from .ragtruth_answer_contract import ragtruth_json_answer

    json_answer, repair_attempted, repair_succeeded = ragtruth_json_answer(raw_answer)
    source = "ragtruth_contract" if json_answer else "ragtruth_contract_error"
    prediction["answer_for_user"] = json_answer
    prediction["answer_for_scoring"] = json_answer
    prediction["answer_finalization"] = {
        "mode": mode,
        "source": source,
        "repetition_removed": False,
        "repetition_kind": "",
        "ragtruth_json_repair_attempted": repair_attempted,
        "ragtruth_json_repair_succeeded": repair_succeeded,
        "ragtruth_json_valid": bool(json_answer),
        "task_contract_status": "ok" if json_answer else "error",
    }


def attach_structured_citations_from_evidence(
    prediction: dict[str, Any],
    *,
    span: str = "",
) -> list[dict[str, str]]:
    if prediction.get("predicted_citations") or prediction.get("structured_citations"):
        return []
    if _is_unanswerable_text(str(span or "").strip().lower()):
        return []
    canonical_sources = _canonical_source_refs(prediction)
    all_candidates = _citation_candidate_items(prediction)
    calculation_matches = (
        calculation_citation_items(prediction, all_candidates)
        if typed_calculation_is_verified(prediction)
        else []
    )
    calculation_citations = [
        citation
        for match in calculation_matches
        if (
            citation := _citation_from_item(
                match.item,
                span=span,
                canonical_sources=canonical_sources,
                source_backrefs=_canonical_source_backrefs(match.item),
                evidence_identity=match.citation_identity,
            )
        )
    ]
    verified_citations = []
    verified_items = minimum_verified_claim_support_items(
        prediction,
        all_candidates,
        span=span,
    )
    record_verified_claim_support(
        prediction,
        [
            *[match.item for match in calculation_matches],
            *verified_items,
        ],
    )
    for item in verified_items:
        citation = _citation_from_item(
            item,
            span=span,
            canonical_sources=canonical_sources,
            source_backrefs=_canonical_source_backrefs(item),
        )
        if citation:
            verified_citations.append(citation)
    return _unique_citations([*calculation_citations, *verified_citations])


def _canonicalized_existing_citations(
    prediction: dict[str, Any],
    *,
    span: str,
) -> list[dict[str, str]]:
    existing = _existing_structured_citations(prediction, span=span)
    if not existing:
        return []
    canonical_sources = _canonical_source_refs(prediction)
    source_alias_map = _canonical_source_alias_map(prediction, canonical_sources)
    citations: list[dict[str, str]] = []
    for item in existing:
        citation = _canonicalized_citation_item(
            item,
            canonical_sources=canonical_sources,
            source_alias_map=source_alias_map,
            span=span,
        )
        if citation:
            citations.append(citation)
    return _unique_citations(citations)


def _existing_structured_citations(
    prediction: dict[str, Any],
    *,
    span: str,
) -> list[dict[str, str]]:
    citations = [
        _normalize_structured_citation(item)
        for item in prediction.get("structured_citations") or []
        if isinstance(item, dict)
    ]
    if citations:
        return citations
    return [
        citation
        for citation in (
            _citation_from_source_ref(str(item), span=span)
            for item in prediction.get("predicted_citations") or []
        )
        if citation
    ]


def _canonicalized_citation_item(
    citation: dict[str, str],
    *,
    canonical_sources: list[str],
    source_alias_map: dict[str, tuple[str, ...]],
    span: str,
) -> dict[str, str]:
    source_id = str(citation.get("source_id") or "").strip()
    page_label = str(citation.get("page_label") or "").strip()
    if source_id and not is_uuid_like_source_id(source_id):
        return citation
    source_ref = _matching_canonical_source_ref(
        canonical_sources,
        page_label,
        source_id=source_id,
        source_aliases=source_alias_map.get(source_id, ()),
    )
    if not source_ref:
        return citation
    canonical = _citation_from_source_ref(source_ref, span=span)
    if not canonical:
        return citation
    kind = str(citation.get("kind") or "").strip()
    if kind:
        canonical["kind"] = kind
    evidence_id = str(citation.get("evidence_id") or "").strip()
    if evidence_id:
        canonical["evidence_id"] = evidence_id
    return canonical


def _unique_citations(citations: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for citation in citations:
        key = (
            str(citation.get("kind") or ""),
            str(citation.get("source_id") or ""),
            str(citation.get("page_label") or ""),
            str(citation.get("evidence_id") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(citation)
    return output


def _extract_structured_answer(answer: str) -> dict[str, Any] | None:
    for candidate in _json_candidates(answer):
        parsed = _parse_json(candidate)
        if not isinstance(parsed, dict):
            continue
        if "answer" not in parsed:
            continue
        citations = parsed.get("citations") or []
        if not isinstance(citations, list):
            citations = []
        return {
            "answer": str(parsed.get("answer") or "").strip(),
            "citations": [_normalize_structured_citation(item) for item in citations],
        }
    return None


def _extract_truncated_structured_answer(answer: str) -> str:
    text = str(answer or "").strip()
    if not text.startswith("{"):
        return ""
    match = _TRUNCATED_JSON_ANSWER_RE.search(text)
    if not match:
        return ""
    try:
        return json.loads(f'"{match.group(1)}"').strip()
    except json.JSONDecodeError:
        return match.group(1).strip()


def _normalize_structured_citation(item: Any) -> dict[str, str]:
    if not isinstance(item, dict):
        return {}
    citation = {
        key: str(item.get(key) or "").strip()
        for key in ("kind", "evidence_id", "source_id", "page_label", "span")
        if str(item.get(key) or "").strip()
    }
    if "page_label" not in citation:
        page = str(item.get("page") or "").strip()
        if page:
            citation["page_label"] = page
    return citation


def _citation_candidate_items(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    evidence_bundle = prediction.get("evidence_bundle")
    if isinstance(evidence_bundle, dict):
        items.extend(
            item
            for item in evidence_bundle.get("items") or []
            if isinstance(item, dict)
        )
    evidence_metadata = prediction.get("evidence_metadata")
    if isinstance(evidence_metadata, dict):
        items.extend(
            item
            for item in evidence_metadata.get("execution_operand_evidence") or []
            if isinstance(item, dict)
        )
        items.extend(
            item
            for item in evidence_metadata.get("evidence") or []
            if isinstance(item, dict)
        )
    items.extend(
        item
        for item in prediction.get("retrieved_hits") or []
        if isinstance(item, dict)
    )
    return items


def _canonical_source_refs(prediction: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for item in _citation_candidate_items(prediction):
        for source in _canonical_source_backrefs(item):
            value = str(source or "").strip()
            if value and value not in refs:
                refs.append(value)
    for key in ("scored_predicted_sources", "predicted_sources"):
        for source in prediction.get(key) or []:
            value = str(source or "").strip()
            if (
                value
                and not source_ref_uses_uuid_like_source(value)
                and value not in refs
            ):
                refs.append(value)
    return refs


def _canonical_source_alias_map(
    prediction: dict[str, Any],
    canonical_sources: list[str],
) -> dict[str, tuple[str, ...]]:
    canonical_ids = {
        str(source).split("#", 1)[0]
        for source in canonical_sources
        if str(source or "").strip()
    }
    aliases: dict[str, list[str]] = {}
    for item in _citation_candidate_items(prediction):
        runtime_ids = [
            str(item.get(key) or "").strip()
            for key in ("source_id", "document_id", "file_id", "runtime_source_id")
            if str(item.get(key) or "").strip()
        ]
        explicit = [
            str(value or "").strip().split("#", 1)[0]
            for value in (
                *list(item.get("source_aliases") or []),
                *list(item.get("source_backrefs") or []),
            )
            if str(value or "").strip()
        ]
        matched = [value for value in explicit if value in canonical_ids]
        for runtime_id in runtime_ids:
            values = aliases.setdefault(runtime_id, [])
            values.extend(value for value in matched if value not in values)
    return {key: tuple(values) for key, values in aliases.items()}


def _canonical_source_backrefs(item: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for source in item.get("source_backrefs") or []:
        value = str(source or "").strip()
        if value and not source_ref_uses_uuid_like_source(value):
            refs.append(value)
    return refs


def _render_structured_answer_for_user(structured: dict[str, Any]) -> str:
    answer = str(structured.get("answer") or "").strip()
    citations = _citation_texts(list(structured.get("citations") or []))
    return " ".join(part for part in [answer, " ".join(citations)] if part).strip()


def _citation_texts(citations: list[dict[str, str]]) -> list[str]:
    output: list[str] = []
    for item in citations:
        source_id = str(item.get("source_id") or "").strip()
        page_label = str(item.get("page_label") or "").strip()
        evidence_id = str(item.get("evidence_id") or "").strip()
        citation = ""
        if source_id and page_label:
            citation = f"{source_id}#page:{page_label}"
        elif source_id:
            citation = f"{source_id}#source"
        elif evidence_id:
            citation = f"{evidence_id}#evidence:{evidence_id}"
        if citation and citation not in output:
            output.append(citation)
    return output


def _json_candidates(answer: str) -> list[str]:
    text = str(answer or "").strip()
    candidates = [match.group(1).strip() for match in _JSON_BLOCK_RE.finditer(text)]
    candidates.append(text)
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if 0 <= first_brace < last_brace:
        candidates.append(text[first_brace : last_brace + 1])
    return [candidate for candidate in candidates if candidate]


def _parse_json(candidate: str) -> Any:
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None
