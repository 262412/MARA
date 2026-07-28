from __future__ import annotations

from typing import Any

from ktem.docqa.evidence_text import extract_final_answer_text

from .answer_metric_core import core_answer_metrics
from .citation_metrics import citation_precision_score, citation_recall_score
from .element_locator_metrics import element_locator_hit_score
from .engine_context import extract_citations
from .indexed_citations import indexed_inline_citations
from .metrics import (
    cross_page_evidence_hit_score,
    element_hit_score,
    false_abstention_score,
    hard_negative_rejection_score,
    image_quote_hit_score,
    is_abstention_answer,
    latex_renderable_score,
    markdown_table_renderable_score,
    modality_hit_score,
    multimodal_support_score,
    page_hit_score,
    span_recall_score,
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
    "pipeline_planning_seconds",
    "pipeline_retrieval_seconds",
    "pipeline_generation_seconds",
    "pipeline_retry_seconds",
    "pipeline_verification_seconds",
    "pipeline_finalization_seconds",
    "answerability_seconds",
    "answer_finalization_seconds",
)
_TOTAL_TIMING_KEYS = (
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
    if abstained and any(
        str(answer or "").strip() and not is_abstention_answer(str(answer))
        for answer in gold_answers
    ):
        false_abstention = 1.0

    strict_page_hit = page_hit_score(
        prediction["predicted_pages"],
        prediction["gold_pages"],
    )
    equivalent_page_hit = evidence_aligned_page_hit_score(
        prediction["predicted_pages"],
        prediction["gold_pages"],
        gold_evidence=list(prediction.get("gold_evidence") or []),
        evidence_bundle=dict(prediction.get("evidence_bundle") or {}),
        retrieved_hits=list(prediction.get("retrieved_hits") or []),
    )
    page_hit = strict_page_hit
    if page_hit == 0.0:
        page_hit = equivalent_page_hit

    metrics = core_answer_metrics(
        prediction,
        predicted_answer=predicted_answer,
        gold_answers=gold_answers,
        abstained=abstained,
        false_abstention=false_abstention,
        page_scores=(page_hit, strict_page_hit, equivalent_page_hit),
        format_scores=(markdown_table_score, latex_score),
        rewrite_skipped=bool(claim_verification.get("rewrite_skipped")),
    )
    metrics["guardrail_expectation_match"] = _guardrail_expectation_match(
        prediction, abstained
    )
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
        or _structured_abstention(prediction)
        or _guardrail_abstained(prediction)
        or is_abstention_answer(predicted_answer)
    )


def _structured_abstention(prediction: dict[str, Any]) -> bool:
    route = (
        str(prediction.get("effective_route") or prediction.get("route") or "")
        .strip()
        .lower()
    )
    if route == "abstain":
        return True
    metadata = dict(prediction.get("evidence_metadata") or {})
    trace = metadata.get("answerability_contract_trace")
    if isinstance(trace, dict) and is_abstention_answer(
        str(trace.get("post_contract_answer") or "")
    ):
        return True
    qasper = metadata.get("qasper_answerability")
    if isinstance(qasper, dict) and str(qasper.get("action") or "").startswith(
        "abstained_"
    ):
        return True
    for value in (
        prediction.get("verify_decision"),
        prediction.get("retrieval_decision"),
        metadata.get("verify_decision"),
        metadata.get("retrieval_decision"),
    ):
        if not isinstance(value, dict):
            continue
        action = str(value.get("action") or "").strip().lower()
        status = str(value.get("status") or "").strip().lower()
        if action == "abstain" or status in {
            "insufficient",
            "insufficient_evidence",
            "not_enough_evidence",
        }:
            return True
    return False


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
    emitted_citations = _emitted_citations_for_scoring(prediction)
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
        emitted_citations,
        gold_evidence,
        evidence_bundle=dict(prediction.get("evidence_bundle") or {}),
        retrieved_hits=list(prediction.get("retrieved_hits") or []),
    )
    metrics["citation_precision"] = citation_precision_score(
        emitted_citations,
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
    _add_citation_locator_metrics(metrics, prediction, gold_evidence, emitted_citations)
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
    answer = str(prediction.get("predicted_answer") or "")
    citations = [
        *extract_citations(answer),
        *indexed_inline_citations(
            answer,
            list(prediction.get("retrieved_hits") or []),
        ),
    ]
    return list(dict.fromkeys(citations))


def _emitted_citations_for_scoring(prediction: dict[str, Any]) -> list[str]:
    metadata = dict(prediction.get("evidence_metadata") or {})
    bundle = prediction.get("evidence_bundle")
    bundle_metadata = (
        dict(bundle.get("metadata") or {}) if isinstance(bundle, dict) else {}
    )
    citations = [
        *_structured_citations_for_scoring(prediction),
        *_inline_citations_for_scoring(prediction),
    ]
    emitted_items = [
        *(metadata.get("emitted_citation_evidence") or []),
        *(bundle_metadata.get("emitted_citation_evidence") or []),
    ]
    for item in emitted_items:
        if not isinstance(item, dict):
            continue
        refs = item.get("source_backrefs")
        if isinstance(refs, str):
            refs = [refs]
        citations.extend(
            str(value).strip() for value in refs or [] if str(value).strip()
        )
        source_id = str(
            item.get("source_id")
            or item.get("document_id")
            or item.get("file_id")
            or ""
        ).strip()
        page_label = str(item.get("page_label") or item.get("page") or "").strip()
        if source_id and page_label:
            citations.append(f"{source_id}#page:{page_label}")
        elif source_id:
            citations.append(f"{source_id}#source")
    return list(dict.fromkeys(value for value in citations if value))


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
        "total_seconds": round(
            sum(timings.get(key, 0.0) for key in _TOTAL_TIMING_KEYS),
            4,
        ),
    }
