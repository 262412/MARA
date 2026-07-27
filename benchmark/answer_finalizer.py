from __future__ import annotations

import json
import re
from typing import Any

from .answer_modes import normalize_benchmark_answer_mode
from .answer_repetition import deduplicate_final_answer as _deduplicate_final_answer
from .answer_scoring_adapter import select_scoring_answer
from .calculation_citation_projection import calculation_citation_items
from .ragtruth_answer_contract import ragtruth_finalization_metadata

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_TRUNCATED_JSON_ANSWER_RE = re.compile(
    r'"answer"\s*:\s*"((?:\\.|[^"\\])*)"',
    re.DOTALL,
)
_UUID_LIKE_SOURCE_RE = re.compile(
    r"^(?:[0-9a-f]{32}|[0-9a-f]{8}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$",
    re.IGNORECASE,
)


def finalize_prediction_answer(
    prediction: dict[str, Any],
    *,
    dataset_name: str,
    mode: str,
) -> None:
    normalized_mode = normalize_benchmark_answer_mode(mode)
    raw_answer = str(prediction.get("predicted_answer") or "")
    if _is_ragtruth_dataset(dataset_name):
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
    prediction["answer_finalization"][
        "qasper_contract_normalized"
    ] = qasper_contract_normalized


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
        if mode != "product" and _should_attach_metadata_citations(
            dataset_name, prediction
        ):
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
    if mode != "product" and _should_attach_metadata_citations(
        dataset_name, prediction
    ):
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


def _is_ragtruth_dataset(dataset_name: str) -> bool:
    return "ragtruth" in str(dataset_name or "").strip().lower()


def _normalize_qasper_contract_answer(
    answer: str,
    *,
    prediction: dict[str, Any],
    dataset_name: str,
) -> tuple[str, bool]:
    dataset = str(dataset_name or "").lower()
    if "qasper" not in dataset:
        return answer, False
    answer_type = str(prediction.get("answer_type") or "").strip().lower()
    normalized = " ".join(str(answer or "").strip().lower().split())
    boolean_match = re.match(r"^(yes|no|true|false)\b", normalized)
    if "qasper_typed" in dataset:
        if boolean_match:
            return ("yes" if boolean_match.group(1) in {"yes", "true"} else "no"), True
        if _is_unanswerable_text(normalized):
            return "unanswerable", True
        return "unanswerable", True
    if answer_type == "boolean":
        if not boolean_match:
            return answer, False
        return ("yes" if boolean_match.group(1) in {"yes", "true"} else "no"), True
    if _is_unanswerable_text(normalized):
        return "unanswerable", True
    return answer, False


def _is_unanswerable_text(answer: str) -> bool:
    return answer.startswith(
        (
            "unanswerable",
            "insufficient evidence",
            "not enough evidence",
            "unable to answer",
            "cannot answer",
        )
    )


def attach_structured_citations_from_evidence(
    prediction: dict[str, Any],
    *,
    span: str = "",
) -> list[dict[str, str]]:
    if prediction.get("predicted_citations") or prediction.get("structured_citations"):
        return []
    canonical_sources = _canonical_source_refs(prediction)
    calculation_citations = [
        citation
        for item in calculation_citation_items(
            prediction,
            _citation_candidate_items(prediction),
        )
        if (
            citation := _citation_from_item(
                item,
                span=span,
                canonical_sources=canonical_sources,
            )
        )
    ]
    if calculation_citations:
        return _unique_citations(calculation_citations)
    for item in _citation_candidate_items(prediction):
        citation = _citation_from_item(
            item,
            span=span,
            canonical_sources=canonical_sources,
        )
        if citation:
            return [citation]
    for source in canonical_sources:
        citation = _citation_from_source_ref(str(source), span=span)
        if citation:
            return [citation]
    return []


def _canonicalized_existing_citations(
    prediction: dict[str, Any],
    *,
    span: str,
) -> list[dict[str, str]]:
    existing = _existing_structured_citations(prediction, span=span)
    if not existing:
        return []
    canonical_sources = _canonical_source_refs(prediction)
    citations: list[dict[str, str]] = []
    for item in existing:
        citation = _canonicalized_citation_item(
            item,
            canonical_sources=canonical_sources,
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
    span: str,
) -> dict[str, str]:
    source_id = str(citation.get("source_id") or "").strip()
    page_label = str(citation.get("page_label") or "").strip()
    if source_id and not _is_uuid_like_source_id(source_id):
        return citation
    source_ref = _matching_canonical_source_ref(canonical_sources, page_label)
    if not source_ref:
        return citation
    canonical = _citation_from_source_ref(source_ref, span=span)
    if not canonical:
        return citation
    evidence_id = str(citation.get("evidence_id") or "").strip()
    if evidence_id:
        canonical["evidence_id"] = evidence_id
    return canonical


def _is_uuid_like_source_id(source_id: str) -> bool:
    return bool(_UUID_LIKE_SOURCE_RE.fullmatch(str(source_id or "").strip()))


def _source_ref_uses_uuid_like_source(source_ref: str) -> bool:
    source_id = str(source_ref or "").strip().split("#", 1)[0]
    return _is_uuid_like_source_id(source_id)


def _unique_citations(citations: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for citation in citations:
        key = (
            str(citation.get("source_id") or ""),
            str(citation.get("page_label") or ""),
            str(citation.get("evidence_id") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(citation)
    return output


def _should_attach_metadata_citations(
    dataset_name: str,
    prediction: dict[str, Any],
) -> bool:
    dataset = str(dataset_name or "").lower()
    return bool(prediction.get("gold_evidence")) or any(
        family in dataset
        for family in ("financebench", "slidevqa", "mmdocrag", "vidore")
    )


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
        for key in ("evidence_id", "source_id", "page_label", "span")
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
            for item in evidence_metadata.get("evidence") or []
            if isinstance(item, dict)
        )
    items.extend(
        item
        for item in prediction.get("retrieved_hits") or []
        if isinstance(item, dict)
    )
    return items


def _citation_from_item(
    item: dict[str, Any],
    *,
    span: str,
    canonical_sources: list[str],
) -> dict[str, str]:
    page_label = _first_nonempty_value(
        item.get("page_label"),
        item.get("page"),
        item.get("page_number"),
    )
    source_ref = _first_nonempty_value(
        *_canonical_source_backrefs(item),
        _matching_canonical_source_ref(canonical_sources, page_label),
    )
    if source_ref:
        parsed = _citation_from_source_ref(source_ref, span=span)
        source_id = parsed.get("source_id", "")
        page_label = parsed.get("page_label", "") or page_label
    else:
        source_id = _first_nonempty_value(
            item.get("source_id"),
            item.get("document_id"),
            item.get("file_id"),
            item.get("runtime_source_id"),
        )
    if not source_id and not page_label:
        return {}
    citation = {
        key: value
        for key, value in {
            "evidence_id": _first_nonempty_value(item.get("evidence_id")),
            "source_id": source_id,
            "page_label": page_label,
            "span": str(span or "").strip(),
        }.items()
        if value
    }
    return citation


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
                and not _source_ref_uses_uuid_like_source(value)
                and value not in refs
            ):
                refs.append(value)
    return refs


def _canonical_source_backrefs(item: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for source in item.get("source_backrefs") or []:
        value = str(source or "").strip()
        if value and not _source_ref_uses_uuid_like_source(value):
            refs.append(value)
    return refs


def _matching_canonical_source_ref(sources: list[str], page_label: str) -> str:
    if page_label:
        suffix = f"#page:{page_label}"
        for source in sources:
            if str(source or "").strip().endswith(suffix):
                return str(source).strip()
    return sources[0] if sources else ""


def _citation_from_source_ref(source_ref: str, *, span: str) -> dict[str, str]:
    value = str(source_ref or "").strip()
    if not value:
        return {}
    if "#page:" in value:
        source_id, page_label = value.split("#page:", 1)
        return {
            key: item
            for key, item in {
                "source_id": source_id.strip(),
                "page_label": page_label.strip(),
                "span": str(span or "").strip(),
            }.items()
            if item
        }
    if "#source" in value:
        source_id = value.split("#source", 1)[0].strip()
        return {
            key: item
            for key, item in {
                "source_id": source_id,
                "span": str(span or "").strip(),
            }.items()
            if item
        }
    return {"source_id": value, "span": str(span or "").strip()} if value else {}


def _first_nonempty_value(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


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
