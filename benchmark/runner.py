from __future__ import annotations

from statistics import mean
from typing import Any

from .manifest import load_manifest
from .metrics import (
    anls_score,
    citation_recall_score,
    element_hit_score,
    exact_match_score,
    formula_normalized_match_score,
    numeric_tolerance_score,
    page_hit_score,
    recall_score,
    round_metric,
    safe_mean,
    span_recall_score,
    token_f1_score,
)
from .schemas import BenchmarkConfig
from .system import KotaemonTextRAGSystem


def _score_prediction(prediction: dict[str, Any]) -> dict[str, float | None]:
    gold_answers = prediction["gold_answers"]
    predicted_answer = prediction["predicted_answer"]
    metrics = {
        "em": exact_match_score(predicted_answer, gold_answers),
        "f1": token_f1_score(predicted_answer, gold_answers),
        "anls": anls_score(predicted_answer, gold_answers),
        "formula_match": formula_normalized_match_score(
            predicted_answer, gold_answers
        ),
        "numeric_match": numeric_tolerance_score(predicted_answer, gold_answers),
        "page_hit": page_hit_score(
            prediction["predicted_pages"], prediction["gold_pages"]
        ),
        "citation_recall": recall_score(
            prediction["predicted_sources"], prediction["gold_sources"]
        ),
    }
    gold_evidence = prediction.get("gold_evidence", [])
    if gold_evidence:
        metrics["element_hit"] = element_hit_score(
            prediction.get("predicted_element_ids", []), gold_evidence
        )
        metrics["span_recall"] = span_recall_score(predicted_answer, gold_evidence)
        metrics["citation_recall"] = citation_recall_score(
            prediction["predicted_sources"], gold_evidence
        )
    return metrics


def run_benchmark(manifest_path: str, config: BenchmarkConfig) -> dict[str, Any]:
    bundle = load_manifest(manifest_path)
    system = KotaemonTextRAGSystem(config)
    predictions: list[dict[str, Any]] = []

    for example in bundle.examples:
        document = bundle.documents[example.document_id]
        try:
            prediction = system.run_example(document, example)
            prediction["error"] = None
        except Exception as exc:
            prediction = {
                "example_id": example.example_id,
                "document_id": document.document_id,
                "document_path": str(document.path),
                "question": example.question,
                "gold_answers": example.answers,
                "gold_pages": example.evidence_pages,
                "gold_sources": example.evidence_sources,
                "gold_evidence": example.gold_evidence,
                "predicted_answer": "",
                "predicted_pages": [],
                "predicted_sources": [],
                "predicted_element_ids": [],
                "retrieved_hits": [],
                "timings": {
                    "parse_seconds": 0.0,
                    "index_seconds": 0.0,
                    "retrieval_seconds": 0.0,
                    "generation_seconds": 0.0,
                },
                "context_preview": "",
                "error": str(exc),
            }
        prediction["document_path"] = str(document.path)
        prediction["document_ids"] = example.document_ids or [example.document_id]
        prediction["scope"] = example.scope
        prediction["modality"] = example.modality
        prediction["answer_type"] = example.answer_type
        prediction["gold_evidence"] = example.gold_evidence
        prediction["metrics"] = _score_prediction(prediction)
        predictions.append(prediction)

    summary = {
        "dataset_name": bundle.dataset_name,
        "manifest_path": str(bundle.manifest_path),
        "suite_name": config.suite_name,
        "num_documents": len(bundle.documents),
        "num_examples": len(bundle.examples),
        "avg_em": round_metric(mean(item["metrics"]["em"] for item in predictions)),
        "avg_f1": round_metric(mean(item["metrics"]["f1"] for item in predictions)),
        "avg_anls": round_metric(mean(item["metrics"]["anls"] for item in predictions)),
        "avg_page_hit": round_metric(
            safe_mean([item["metrics"]["page_hit"] for item in predictions])
        ),
        "avg_citation_recall": round_metric(
            safe_mean([item["metrics"]["citation_recall"] for item in predictions])
        ),
        "avg_element_hit": round_metric(
            safe_mean([item["metrics"].get("element_hit") for item in predictions])
        ),
        "avg_span_recall": round_metric(
            safe_mean([item["metrics"].get("span_recall") for item in predictions])
        ),
        "avg_formula_match": round_metric(
            safe_mean([item["metrics"]["formula_match"] for item in predictions])
        ),
        "avg_numeric_match": round_metric(
            safe_mean([item["metrics"]["numeric_match"] for item in predictions])
        ),
        "avg_retrieval_seconds": round_metric(
            mean(item["timings"]["retrieval_seconds"] for item in predictions)
        ),
        "avg_generation_seconds": round_metric(
            mean(item["timings"]["generation_seconds"] for item in predictions)
        ),
    }

    return {
        "summary": summary,
        "config": config.to_dict(),
        "documents": system.document_reports(),
        "predictions": predictions,
    }
