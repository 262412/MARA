from __future__ import annotations

from typing import Any

from ktem.docqa.evidence_text import extract_final_answer_text

from .citation_metrics import citation_precision_score, citation_recall_score
from .element_locator_metrics import element_locator_hit_score
from .engine_context import extract_citations
from .metrics import (
    anls_score,
    cross_page_evidence_hit_score,
    element_hit_score,
    exact_match_score,
    false_abstention_score,
    formula_normalized_match_score,
    hard_negative_rejection_score,
    image_quote_hit_score,
    is_abstention_answer,
    latex_renderable_score,
    markdown_table_renderable_score,
    modality_hit_score,
    multimodal_support_score,
    numeric_tolerance_score,
    page_hit_score,
    recall_score,
    span_recall_score,
    token_f1_score,
)
from .page_alignment import evidence_aligned_page_hit_score
from .semantic_answer import SemanticJudge, semantic_answer_metrics
from .verification_metrics import verification_metrics

_TABLE_FORMATS = {"markdown_table", "markdown-table", "table"}
_LATEX_FORMATS = {"latex", "math", "formula", "math_formula", "math-formula"}
_TIMING_KEYS = (
    "parse_seconds",
    "index_seconds",
    "retrieval_seconds",
    "generation_seconds",
)
_CACHE_KEYS = ("hits", "misses", "writes")


def score_prediction(
    prediction: dict[str, Any],
    *,
    answer_key: str | None = None,
    semantic_judge: SemanticJudge | None = None,
) -> dict[str, float | None]:
    gold_answers = prediction["gold_answers"]
    expected_formats = _normalized_expected_formats(prediction)
    formatted_answer = _answer_text_for_scoring(
        _prediction_answer_text(prediction, answer_key=answer_key),
        expected_formats=expected_formats,
    )
    presentation_answer = _answer_text_for_scoring(
        _prediction_answer_text(
            prediction,
            answer_key=answer_key or "predicted_answer",
        ),
        expected_formats=expected_formats,
    )
    predicted_answer = _collapse_scoring_text(formatted_answer)
    claim_verification = dict(prediction.get("claim_verification") or {})
    abstained = _prediction_abstained(prediction, predicted_answer, claim_verification)
    markdown_table_score = markdown_table_renderable_score(presentation_answer)
    latex_score = latex_renderable_score(presentation_answer)
    if expected_formats & _TABLE_FORMATS and markdown_table_score is None:
        markdown_table_score = 0.0
    if expected_formats & _LATEX_FORMATS and latex_score is None:
        latex_score = 0.0
    false_abstention = false_abstention_score(predicted_answer, gold_answers)
    if abstained and any(str(answer or "").strip() for answer in gold_answers):
        false_abstention = 1.0

    page_hit = page_hit_score(prediction["predicted_pages"], prediction["gold_pages"])
    if page_hit == 0.0:
        page_hit = evidence_aligned_page_hit_score(
            prediction["predicted_pages"],
            prediction["gold_pages"],
            gold_evidence=list(prediction.get("gold_evidence") or []),
            evidence_bundle=dict(prediction.get("evidence_bundle") or {}),
            retrieved_hits=list(prediction.get("retrieved_hits") or []),
        )

    metrics = {
        "em": exact_match_score(predicted_answer, gold_answers),
        "f1": token_f1_score(predicted_answer, gold_answers),
        "anls": anls_score(predicted_answer, gold_answers),
        "formula_match": formula_normalized_match_score(predicted_answer, gold_answers),
        "numeric_match": numeric_tolerance_score(predicted_answer, gold_answers),
        "page_hit": page_hit,
        "citation_recall": recall_score(
            prediction["predicted_sources"], prediction["gold_sources"]
        ),
        "abstained": float(abstained),
        "false_abstention": false_abstention,
        "markdown_table_renderable": markdown_table_score,
        "latex_renderable": latex_score,
        "rewrite_skipped": float(bool(claim_verification.get("rewrite_skipped"))),
        "guardrail_expectation_match": _guardrail_expectation_match(
            prediction, abstained
        ),
    }
    _add_modality_metrics(metrics, prediction)
    metrics.update(verification_metrics(prediction))
    _add_gold_evidence_metrics(metrics, prediction, predicted_answer)
    if answer_key in {None, "answer_for_scoring"}:
        semantic_metrics, semantic_metadata = semantic_answer_metrics(
            prediction,
            judge=semantic_judge,
        )
        metrics.update(semantic_metrics)
        prediction["semantic_answer_evaluation"] = semantic_metadata
    return metrics


def _prediction_answer_text(
    prediction: dict[str, Any],
    *,
    answer_key: str | None,
) -> str:
    if answer_key:
        return str(prediction.get(answer_key) or "")
    if "answer_for_scoring" in prediction:
        return str(prediction.get("answer_for_scoring") or "")
    return str(prediction.get("predicted_answer") or "")


def _answer_text_for_scoring(answer: Any, *, expected_formats: set[str]) -> str:
    text = extract_final_answer_text(str(answer or "")).replace("**", "")
    if not expected_formats & _TABLE_FORMATS:
        without_tables = _remove_markdown_table_lines(text)
        if without_tables.strip():
            text = without_tables
    return _clean_scoring_lines(text)


def _clean_scoring_lines(text: str) -> str:
    lines = [line.strip() for line in str(text or "").splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _collapse_scoring_text(text: str) -> str:
    return " ".join(str(text or "").split())


def _remove_markdown_table_lines(text: str) -> str:
    return "\n".join(
        line
        for line in str(text or "").splitlines()
        if not _is_markdown_table_line(line)
    )


def _is_markdown_table_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return False
    cells = [cell.strip() for cell in stripped.strip("|").split("|")]
    return len(cells) > 1


def normalize_operational_fields(prediction: dict[str, Any]) -> None:
    timings = _normalize_timings(prediction.get("timings"))
    prediction["timings"] = timings

    performance = dict(prediction.get("performance") or {})
    for key, value in _performance_from_timings(timings).items():
        performance.setdefault(key, value)
    prediction["performance"] = performance
    prediction["cache"] = _normalize_cache(prediction.get("cache"))
    prediction["cost"] = dict(prediction.get("cost") or {})


def _normalized_expected_formats(prediction: dict[str, Any]) -> set[str]:
    return {
        str(item).strip().lower()
        for item in prediction.get("expected_formats", [])
        if str(item).strip()
    }


def _guardrail_abstained(prediction: dict[str, Any]) -> bool:
    guardrail = dict(prediction.get("guardrail_decision") or {})
    action = str(guardrail.get("action") or "").strip().lower()
    status = str(guardrail.get("status") or "").strip().lower()
    if action == "abstain":
        return True
    if action == "revise":
        return False
    return status == "not_enough_evidence"


def _prediction_abstained(
    prediction: dict[str, Any],
    predicted_answer: str,
    claim_verification: dict[str, Any],
) -> bool:
    return (
        bool(claim_verification.get("abstained"))
        or _guardrail_abstained(prediction)
        or is_abstention_answer(predicted_answer)
    )


def _guardrail_expectation_match(
    prediction: dict[str, Any],
    abstained: bool,
) -> float | None:
    expected = dict(prediction.get("expected_guardrails") or {})
    if not expected:
        return None

    claim_verification = dict(prediction.get("claim_verification") or {})
    checks: list[bool] = []
    if "rewrite_skipped" in expected:
        checks.append(
            bool(claim_verification.get("rewrite_skipped"))
            == bool(expected["rewrite_skipped"])
        )
    if "allow_abstention" in expected:
        checks.append(bool(expected["allow_abstention"]) or not abstained)
    if not checks:
        return None
    return sum(1 for item in checks if item) / len(checks)


def _add_modality_metrics(
    metrics: dict[str, float | None],
    prediction: dict[str, Any],
) -> None:
    for modality in ("table", "figure", "formula", "slide"):
        metrics[f"{modality}_hit"] = modality_hit_score(
            modality,
            expected_modality=str(prediction.get("modality") or ""),
            evidence_metadata=dict(prediction.get("evidence_metadata") or {}),
            retrieved_hits=list(prediction.get("retrieved_hits") or []),
            gold_evidence=list(prediction.get("gold_evidence") or []),
        )


def _add_gold_evidence_metrics(
    metrics: dict[str, float | None],
    prediction: dict[str, Any],
    predicted_answer: str,
) -> None:
    gold_evidence = prediction.get("gold_evidence", [])
    if not gold_evidence:
        return
    inline_citations = _inline_citations_for_scoring(prediction)
    metadata_citations = _metadata_citations_for_scoring(prediction)
    predicted_citations = inline_citations or metadata_citations
    metrics["element_hit"] = element_hit_score(
        prediction.get("predicted_element_ids", []), gold_evidence
    )
    metrics["element_locator_hit"] = element_locator_hit_score(
        list(prediction.get("retrieved_hits") or []), gold_evidence
    )
    metrics["span_recall"] = span_recall_score(predicted_answer, gold_evidence)
    metrics["image_quote_hit"] = image_quote_hit_score(predicted_answer, gold_evidence)
    metrics["multimodal_answer_support"] = multimodal_support_score(
        evidence_bundle=dict(prediction.get("evidence_bundle") or {}),
        retrieved_hits=list(prediction.get("retrieved_hits") or []),
        gold_evidence=gold_evidence,
    )
    metrics["hard_negative_rejection"] = hard_negative_rejection_score(
        evidence_bundle=dict(prediction.get("evidence_bundle") or {}),
        retrieved_hits=list(prediction.get("retrieved_hits") or []),
        gold_evidence=gold_evidence,
    )
    metrics["citation_recall"] = citation_recall_score(
        predicted_citations,
        gold_evidence,
        evidence_bundle=dict(prediction.get("evidence_bundle") or {}),
        retrieved_hits=list(prediction.get("retrieved_hits") or []),
    )
    metrics["citation_precision"] = citation_precision_score(
        predicted_citations,
        gold_evidence,
        evidence_bundle=dict(prediction.get("evidence_bundle") or {}),
        retrieved_hits=list(prediction.get("retrieved_hits") or []),
    )
    _add_citation_group_metrics(
        metrics,
        "citation_inline",
        inline_citations,
        gold_evidence,
        prediction,
    )
    _add_citation_group_metrics(
        metrics,
        "citation_metadata",
        metadata_citations,
        gold_evidence,
        prediction,
    )
    _add_citation_locator_metrics(
        metrics, prediction, gold_evidence, predicted_citations
    )
    _add_citation_locator_metrics(
        metrics,
        prediction,
        gold_evidence,
        inline_citations,
        metric_prefix="citation_inline",
    )
    _add_citation_locator_metrics(
        metrics,
        prediction,
        gold_evidence,
        metadata_citations,
        metric_prefix="citation_metadata",
    )
    metrics["cross_page_evidence_hit"] = cross_page_evidence_hit_score(
        prediction["predicted_pages"],
        evidence_bundle=dict(prediction.get("evidence_bundle") or {}),
        retrieved_hits=list(prediction.get("retrieved_hits") or []),
        gold_evidence=gold_evidence,
    )


def _add_citation_locator_metrics(
    metrics: dict[str, float | None],
    prediction: dict[str, Any],
    gold_evidence: list[dict[str, Any]],
    predicted_citations: list[str],
    *,
    metric_prefix: str = "citation",
) -> None:
    evidence_bundle = dict(prediction.get("evidence_bundle") or {})
    retrieved_hits = list(prediction.get("retrieved_hits") or [])
    for locator_kind in ("source", "page", "span"):
        locator_gold = [
            item
            for item in gold_evidence
            if _gold_evidence_has_locator(item, locator_kind)
        ]
        metrics[f"{metric_prefix}_recall_{locator_kind}"] = citation_recall_score(
            predicted_citations,
            locator_gold,
            evidence_bundle=evidence_bundle,
            retrieved_hits=retrieved_hits,
        )
        metrics[f"{metric_prefix}_precision_{locator_kind}"] = citation_precision_score(
            predicted_citations,
            locator_gold,
            evidence_bundle=evidence_bundle,
            retrieved_hits=retrieved_hits,
        )


def _add_citation_group_metrics(
    metrics: dict[str, float | None],
    metric_prefix: str,
    predicted_citations: list[str],
    gold_evidence: list[dict[str, Any]],
    prediction: dict[str, Any],
) -> None:
    evidence_bundle = dict(prediction.get("evidence_bundle") or {})
    retrieved_hits = list(prediction.get("retrieved_hits") or [])
    metrics[f"{metric_prefix}_recall"] = citation_recall_score(
        predicted_citations,
        gold_evidence,
        evidence_bundle=evidence_bundle,
        retrieved_hits=retrieved_hits,
    )
    metrics[f"{metric_prefix}_precision"] = citation_precision_score(
        predicted_citations,
        gold_evidence,
        evidence_bundle=evidence_bundle,
        retrieved_hits=retrieved_hits,
    )


def _inline_citations_for_scoring(prediction: dict[str, Any]) -> list[str]:
    predicted_citations = list(prediction.get("predicted_citations") or [])
    if predicted_citations:
        return predicted_citations
    structured_citations = _structured_citations_for_scoring(prediction)
    if structured_citations:
        return structured_citations
    return extract_citations(str(prediction.get("predicted_answer") or ""))


def _metadata_citations_for_scoring(prediction: dict[str, Any]) -> list[str]:
    scored_sources = list(prediction.get("scored_predicted_sources") or [])
    if scored_sources:
        return scored_sources
    return list(prediction["predicted_sources"])


def _structured_citations_for_scoring(prediction: dict[str, Any]) -> list[str]:
    citations = []
    for item in prediction.get("structured_citations") or []:
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("source_id") or "").strip()
        page_label = str(item.get("page_label") or item.get("page") or "").strip()
        evidence_id = str(item.get("evidence_id") or "").strip()
        citation = ""
        if source_id and page_label:
            citation = f"{source_id}#page:{page_label}"
        elif source_id:
            citation = f"{source_id}#source"
        elif evidence_id:
            citation = f"{evidence_id}#evidence:{evidence_id}"
        if citation and citation not in citations:
            citations.append(citation)
    return citations


def _gold_evidence_has_locator(item: dict[str, Any], locator_kind: str) -> bool:
    if locator_kind == "page":
        return _gold_evidence_has_page_locator(item)
    if locator_kind == "source":
        return not _gold_evidence_has_page_locator(item) and any(
            _has_value(item.get(key))
            for key in ("document_id", "source_id", "citation", "source")
        )
    if locator_kind == "span":
        return any(
            _has_value(item.get(key)) for key in ("span", "text", "quote", "evidence")
        )
    return False


def _gold_evidence_has_page_locator(item: dict[str, Any]) -> bool:
    if _has_value(item.get("page")) or _has_value(item.get("page_label")):
        return True
    citation = str(item.get("citation") or item.get("source") or "")
    return "#page" in citation.lower()


def _has_value(value: Any) -> bool:
    return value not in (None, "", [])


def _normalize_timings(timings: dict[str, Any] | None) -> dict[str, float]:
    source = timings or {}
    return {key: round(float(source.get(key, 0.0) or 0.0), 4) for key in _TIMING_KEYS}


def _normalize_cache_stats(stats: dict[str, Any] | None) -> dict[str, int]:
    source = stats or {}
    return {key: int(source.get(key, 0) or 0) for key in _CACHE_KEYS}


def _normalize_cache(cache: dict[str, Any] | None) -> dict[str, Any]:
    source = cache or {}
    return {
        **source,
        "parse": _normalize_cache_stats(source.get("parse")),
        "embedding": _normalize_cache_stats(source.get("embedding")),
    }


def _performance_from_timings(timings: dict[str, float]) -> dict[str, Any]:
    return {
        **timings,
        "total_seconds": round(sum(timings.values()), 4),
    }
