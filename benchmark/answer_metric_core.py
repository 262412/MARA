from __future__ import annotations

from typing import Any

from .metrics import (
    anls_score,
    exact_match_score,
    formula_normalized_match_score,
    legacy_token_f1_score,
    numeric_tolerance_score,
    recall_score,
    token_f1_score,
)


def core_answer_metrics(
    prediction: dict[str, Any],
    *,
    predicted_answer: str,
    gold_answers: list[str],
    abstained: bool,
    false_abstention: float,
    page_scores: tuple[float | None, float | None, float | None],
    format_scores: tuple[float | None, float | None],
    rewrite_skipped: bool,
) -> dict[str, float | None]:
    page_hit, strict_page_hit, equivalent_page_hit = page_scores
    markdown_table_score, latex_score = format_scores
    token_f1_v2 = token_f1_score(predicted_answer, gold_answers)
    return {
        "em": exact_match_score(predicted_answer, gold_answers),
        "f1": token_f1_v2,
        "token_f1_v2": token_f1_v2,
        "legacy_token_f1": legacy_token_f1_score(predicted_answer, gold_answers),
        "anls": anls_score(predicted_answer, gold_answers),
        "formula_match": formula_normalized_match_score(predicted_answer, gold_answers),
        "numeric_match": numeric_tolerance_score(predicted_answer, gold_answers),
        "page_hit": page_hit,
        "strict_page_hit": strict_page_hit,
        "equivalent_evidence_page_hit": equivalent_page_hit,
        "source_retrieval_recall": recall_score(
            prediction["predicted_sources"], prediction["gold_sources"]
        ),
        "predicted_source_recall": recall_score(
            prediction["predicted_sources"], prediction["gold_sources"]
        ),
        "citation_recall": None,
        "citation_precision": None,
        "abstained": float(abstained),
        "false_abstention": false_abstention,
        "markdown_table_renderable": markdown_table_score,
        "latex_renderable": latex_score,
        "rewrite_skipped": float(rewrite_skipped),
    }
