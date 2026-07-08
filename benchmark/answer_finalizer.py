from __future__ import annotations

import json
import re
from typing import Any

from ktem.docqa.evidence_text import extract_final_answer_text

from .answer_modes import normalize_benchmark_answer_mode

_INLINE_CITATION_RE = re.compile(r"\[\s*\d+(?:\s*,\s*\d+)*\s*\]")
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_FINAL_ANSWER_PREFIX_RE = re.compile(
    r"^\s*(?:\*{0,2}\s*)?(?:final\s+answer|answer|最终答案|最终回答)"
    r"(?:\s*\*{0,2})?\s*[:：]\s*",
    re.IGNORECASE,
)
_ANSWER_PRESENTATION_PREFIX_RE = re.compile(
    r"^\s*(?:the\s+answer\s+is|the\s+answer\s+was|answer\s+is|answer\s+was|"
    r"it\s+is|it\s+was)\s+",
    re.IGNORECASE,
)
_LIST_PREFIX_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+")
_YES_NO_RATIONALE_RE = re.compile(r"^\s*(yes|no)[.!?]\s+(.+)", re.IGNORECASE)
_YES_NO_ONLY_RE = re.compile(r"^\s*(yes|no)[.!?]?\s*$", re.IGNORECASE)
_TRUNCATED_JSON_ANSWER_RE = re.compile(
    r'"answer"\s*:\s*"((?:\\.|[^"\\])*)"',
    re.DOTALL,
)
_UUID_LIKE_SOURCE_RE = re.compile(
    r"^(?:[0-9a-f]{32}|[0-9a-f]{8}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$",
    re.IGNORECASE,
)
_INITIAL_PERIOD_TOKEN = "__MARA_INITIAL_PERIOD__"
_INITIAL_PERIOD_RE = re.compile(r"\b([A-Z])\.")


def finalize_prediction_answer(
    prediction: dict[str, Any],
    *,
    dataset_name: str,
    mode: str,
) -> None:
    normalized_mode = normalize_benchmark_answer_mode(mode)
    raw_answer = str(prediction.get("predicted_answer") or "")
    structured_answer = _extract_structured_answer(raw_answer)
    truncated_answer = ""
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
        if normalized_mode != "product" and _should_attach_metadata_citations(
            dataset_name,
            prediction,
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
    if normalized_mode != "product" and _should_attach_metadata_citations(
        dataset_name,
        prediction,
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
    if normalized_mode == "product":
        answer_for_scoring = answer_for_user
        source = "product_answer"
    elif structured_answer is not None:
        answer_for_scoring = _answer_for_scoring(
            structured_answer["answer"],
            dataset_name=dataset_name,
        )
        source = "structured_adapter"
    elif truncated_answer:
        answer_for_scoring = _answer_for_scoring(
            truncated_answer,
            dataset_name=dataset_name,
        )
        source = "truncated_structured_adapter"
    else:
        answer_for_scoring = _answer_for_scoring(
            answer_for_scoring_source,
            dataset_name=dataset_name,
        )
        source = "deterministic_adapter"

    prediction["answer_for_user"] = answer_for_user
    prediction["answer_for_scoring"] = answer_for_scoring
    prediction["answer_finalization"] = {
        "mode": normalized_mode,
        "source": source,
    }


def attach_structured_citations_from_evidence(
    prediction: dict[str, Any],
    *,
    span: str = "",
) -> list[dict[str, str]]:
    if prediction.get("predicted_citations") or prediction.get("structured_citations"):
        return []
    canonical_sources = _canonical_source_refs(prediction)
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


def _answer_for_scoring(answer: str, *, dataset_name: str) -> str:
    dataset = str(dataset_name or "").lower()
    if "ragtruth" in dataset:
        json_answer = _extract_json_answer(answer)
        if json_answer:
            return json_answer
    cleaned = _clean_scoring_text(extract_final_answer_text(answer))
    if "qampari" in dataset:
        return _comma_list_answer(cleaned)
    return _short_answer(cleaned)


def _extract_json_answer(answer: str) -> str:
    for candidate in _json_candidates(answer):
        parsed = _parse_json(candidate)
        if parsed is not None:
            return json.dumps(parsed, ensure_ascii=False)
    return ""


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


def _clean_scoring_text(answer: str) -> str:
    text = str(answer or "").replace("**", "")
    text = _INLINE_CITATION_RE.sub(" ", text)
    lines = [_clean_line(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def _clean_line(line: str) -> str:
    text = _FINAL_ANSWER_PREFIX_RE.sub("", str(line or ""))
    text = _LIST_PREFIX_RE.sub("", text)
    text = _ANSWER_PRESENTATION_PREFIX_RE.sub("", text)
    return " ".join(text.split())


def _comma_list_answer(answer: str) -> str:
    first_line = _first_nonempty_line(answer)
    if "," in first_line:
        parts = [part.strip().rstrip(".") for part in first_line.split(",")]
        return ", ".join(part for part in parts if part)
    return _short_answer(answer)


def _short_answer(answer: str) -> str:
    first_line = _first_nonempty_line(answer)
    if not first_line:
        return ""
    yes_no_rationale = _yes_no_rationale_answer(answer)
    if yes_no_rationale:
        return yes_no_rationale
    if _looks_like_direct_answer(first_line):
        return _strip_terminal_period(first_line)
    return _strip_terminal_period(_first_sentence(first_line))


def _yes_no_rationale_answer(answer: str) -> str:
    lines = [line.strip() for line in str(answer or "").splitlines() if line.strip()]
    if not lines:
        return ""

    same_line = _YES_NO_RATIONALE_RE.match(lines[0])
    if same_line:
        return _format_yes_no_rationale(same_line.group(1), same_line.group(2))

    first_line = _YES_NO_ONLY_RE.fullmatch(lines[0])
    if first_line and len(lines) > 1:
        return _format_yes_no_rationale(first_line.group(1), lines[1])

    return ""


def _format_yes_no_rationale(polarity: str, rationale: str) -> str:
    sentence = _first_sentence(str(rationale or "").strip())
    if not sentence:
        return ""
    return _strip_terminal_period(f"{polarity.capitalize()}. {sentence}")


def _first_nonempty_line(text: str) -> str:
    for line in str(text or "").splitlines():
        value = line.strip()
        if value:
            return value
    return ""


def _looks_like_direct_answer(line: str) -> bool:
    words = line.split()
    if len(words) <= 8:
        return True
    if "," in line and len(words) <= 16:
        return True
    return False


def _first_sentence(text: str) -> str:
    protected = _INITIAL_PERIOD_RE.sub(rf"\1{_INITIAL_PERIOD_TOKEN}", text)
    match = re.search(r"(?<=[.!?])\s+", protected)
    if not match:
        return text
    return protected[: match.start()].replace(_INITIAL_PERIOD_TOKEN, ".")


def _strip_terminal_period(text: str) -> str:
    value = str(text or "").strip()
    if value.endswith(".") and not value.endswith("..."):
        return value[:-1].strip()
    return value
