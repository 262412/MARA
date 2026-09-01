from __future__ import annotations

import json
import re
from typing import Any

from .answer_citation_projection import (
    canonical_source_alias_map as _canonical_source_alias_map,
)
from .answer_citation_projection import (
    canonical_source_backrefs as _canonical_source_backrefs,
)
from .answer_citation_projection import canonical_source_refs as _canonical_source_refs
from .answer_citation_projection import (
    citation_candidate_items as _citation_candidate_items,
)
from .answer_citation_projection import (
    citation_projection_source as _citation_projection_source,
)
from .answer_citation_projection import (
    record_frozen_citation_trace as _record_frozen_citation_trace,
)
from .answer_citation_projection import (
    set_citation_projection_source as _set_citation_projection_source,
)
from .answer_citation_projection import (
    terminal_commit_citations as _terminal_commit_citations,
)
from .answer_modes import normalize_benchmark_answer_mode
from .answer_repetition import deduplicate_final_answer as _deduplicate_final_answer
from .calculation_citation_projection import calculation_citation_items
from .citation_claim_selection import minimum_verified_claim_support_items
from .citation_rendering import citation_from_item as _citation_from_item
from .citation_rendering import citation_from_source_ref as _citation_from_source_ref
from .citation_rendering import (
    matching_canonical_source_ref as _matching_canonical_source_ref,
)
from .citation_stage_projection import (
    frozen_canonical_plan_citation_items,
    is_uuid_like_source_id,
    record_emitted_citation_evidence,
)
from .finance_answer_finalization import (
    enforce_finance_citation_authority,
    metadata_citations_allowed,
)
from .finance_citation_contract import (
    record_execution_operand_evidence,
    record_verified_claim_support,
    typed_calculation_is_verified,
)
from .qasper_answer_normalization import is_unanswerable_text as _is_unanswerable_text
from .qasper_answer_normalization import (
    record_qasper_metadata as _record_qasper_metadata,
)
from .qasper_terminal_commit import qasper_terminal_scoring_commit
from .ragtruth_answer_contract import ragtruth_finalization_metadata
from .ragtruth_answer_finalizer import finalize_ragtruth_prediction
from .standard_answer_finalizer import finalize_standard_prediction

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
    presentation_answer = str(
        prediction.get("answer_for_user") or prediction.get("predicted_answer") or ""
    )
    raw_answer, preserve_semantic_answer = qasper_terminal_scoring_commit(
        prediction,
        dataset_name=dataset_name,
    )
    if _is_ragtruth_dataset(dataset_name):
        finalize_ragtruth_prediction(
            prediction,
            raw_answer=raw_answer,
            dataset_name=dataset_name,
            mode=normalized_mode,
            presentation_answer=presentation_answer,
            preserve_semantic_answer=preserve_semantic_answer,
        )
        return
    finalize_standard_prediction(
        prediction,
        raw_answer=raw_answer,
        dataset_name=dataset_name,
        mode=normalized_mode,
        presentation_answer=presentation_answer,
        preserve_semantic_answer=preserve_semantic_answer,
    )


def _is_ragtruth_dataset(dataset_name: str) -> bool:
    return "ragtruth" in str(dataset_name or "").strip().lower()


def _prepare_finalization_evidence(
    prediction: dict[str, Any], *, dataset_name: str
) -> None:
    record_execution_operand_evidence(
        prediction,
        _citation_candidate_items(prediction),
        _canonical_source_refs(prediction),
    )
    enforce_finance_citation_authority(prediction, dataset_name=dataset_name)


def _finalization_answer_source(
    raw_answer: str,
    *,
    prediction: dict[str, Any],
    dataset_name: str,
    preserve_semantic_answer: bool,
) -> tuple[str, bool, str]:
    if preserve_semantic_answer:
        prediction["predicted_answer"] = raw_answer
        return raw_answer, False, ""
    return _deduplicate_final_answer(
        raw_answer,
        prediction=prediction,
        dataset_name=dataset_name,
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
        projection_source=_citation_projection_source(prediction),
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
    if (
        structured_answer is not None
        and mode != "product"
        and metadata_citations_allowed(dataset_name, prediction)
        and not prediction.get("predicted_citations")
        and not prediction.get("structured_citations")
    ):
        citations = attach_structured_citations_from_evidence(
            prediction,
            span=answer_text_for_user,
        )
        if citations:
            prediction["structured_citations"] = citations
            prediction["predicted_citations"] = _citation_texts(citations)
            answer_for_user = _render_structured_answer_for_user(
                {"answer": answer_text_for_user, "citations": citations}
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
    frozen_items, frozen_trace = frozen_canonical_plan_citation_items(
        prediction,
        all_candidates,
    )
    _record_frozen_citation_trace(prediction, frozen_trace)
    frozen_citations = [
        citation
        for item in frozen_items
        if (
            citation := _citation_from_item(
                item,
                span=span,
                canonical_sources=canonical_sources,
                source_backrefs=_canonical_source_backrefs(item),
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
            *frozen_items,
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
    if frozen_items:
        _set_citation_projection_source(prediction, "frozen_canonical_plan")
    elif calculation_matches:
        _set_citation_projection_source(prediction, "verified_calculation")
    elif verified_items:
        _set_citation_projection_source(prediction, "verified_claim_support")
    return _unique_citations(
        [*calculation_citations, *frozen_citations, *verified_citations]
    )


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
    citations = [
        citation
        for citation in (
            _citation_from_source_ref(str(item), span=span)
            for item in prediction.get("predicted_citations") or []
        )
        if citation
    ]
    if citations:
        return citations
    return _terminal_commit_citations(prediction, span=span)


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
