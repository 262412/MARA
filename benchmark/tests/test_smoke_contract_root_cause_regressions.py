from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.evidence_ranking_trace import materialize_reranked_candidates
from ktem.docqa.source_identity_crosswalk import (
    SourceIdentityCrosswalk,
    SourceIdentityResolver,
    canonicalize_evidence_source,
)

from benchmark.answer_metric_core import core_answer_metrics
from benchmark.contract_gate_metrics import prediction_gate_metrics
from benchmark.contract_invariant_metrics import contract_invariant_summary
from benchmark.evidence_stage_coverage import stage_coverage_values
from benchmark.page_stage_metrics import stage_all_gold_pages_hit
from benchmark.qasper_answerability import verify_qasper_answerability


class _JsonLLM:
    def __init__(self, payload: dict[str, str]):
        self.payload = payload

    def __call__(self, *_args, **_kwargs):
        return SimpleNamespace(text=json.dumps(self.payload))


def _crosswalk() -> list[dict[str, object]]:
    return [
        SourceIdentityCrosswalk(
            canonical_dataset_id="paper-gold-id",
            runtime_file_id="8edc-runtime-uuid",
            runtime_source_id="8edc-runtime-uuid",
            document_path="/datasets/paper.pdf",
            filename="paper.pdf",
            aliases=("paper",),
        ).as_dict()
    ]


def test_gold_document_id_matches_runtime_uuid_alias():
    resolver = SourceIdentityResolver(_crosswalk())

    assert resolver.resolve("8edc-runtime-uuid") == "paper-gold-id"
    assert resolver.resolve("/datasets/paper.pdf") == "paper-gold-id"
    assert resolver.unresolved_count(["paper-gold-id"]) == 0
    assert resolver.ambiguous_alias_count == 0


def test_benchmark_source_projection_preserves_runtime_plan_identity():
    runtime = {
        "source_id": "8edc-runtime-uuid",
        "span_id": "answer-span",
        "text": "The paper uses labeled features.",
    }
    runtime_identity = identity_of(runtime).key

    projected = canonicalize_evidence_source(runtime, _crosswalk())

    assert identity_of(projected).key == runtime_identity
    assert projected["runtime_identity"] == runtime_identity
    assert projected["evaluation_identity"] == ("span:paper-gold-id:answer-span")
    prediction = {
        "question": "What features are used?",
        "evidence_metadata": {
            "canonical_candidate_evidence": [projected],
            "query_plan": {
                "answer_type": "free_text",
                "question_type": "factoid",
                "constraints": {},
                "evidence_slots": [
                    {
                        "slot_id": "support:answer",
                        "role": "support",
                        "required": True,
                        "status": "filled",
                        "evidence_ids": [runtime_identity],
                    }
                ],
            },
        },
    }

    summary = contract_invariant_summary([prediction])

    assert summary["slot_unresolved_reference_count"] == 0.0
    assert summary["slot_semantic_false_fill_count"] == 0.0
    assert summary["plan_evidence_reference_resolution_rate"] == 1.0


def test_unresolved_slot_reference_is_not_a_semantic_false_fill():
    prediction = {
        "question": "What features are used?",
        "evidence_metadata": {
            "canonical_candidate_evidence": [
                {
                    "source_id": "runtime",
                    "span_id": "available",
                    "text": "The paper uses labeled features.",
                }
            ],
            "query_plan": {
                "answer_type": "free_text",
                "question_type": "factoid",
                "constraints": {},
                "evidence_slots": [
                    {
                        "slot_id": "support:answer",
                        "role": "support",
                        "required": True,
                        "status": "filled",
                        "evidence_ids": ["span:runtime:missing"],
                    }
                ],
            },
        },
    }

    summary = contract_invariant_summary([prediction])

    assert summary["slot_unresolved_reference_count"] == 1.0
    assert summary["slot_semantic_false_fill_count"] == 0.0
    assert summary["required_slot_false_fill_count"] == 0.0
    assert summary["plan_evidence_reference_resolution_rate"] == 0.0


def test_source_page_pair_uses_crosswalk():
    prediction = {
        "source_identity_crosswalk": _crosswalk(),
        "gold_evidence": [{"document_id": "paper-gold-id", "page": 7}],
        "evidence_metadata": {
            "selected_evidence": [{"source_id": "8edc-runtime-uuid", "page_label": "7"}]
        },
    }

    assert stage_all_gold_pages_hit(prediction, "selected_evidence") == 1.0


def test_ambiguous_filename_alias_is_not_silently_joined():
    records = [
        {
            "canonical_dataset_id": f"paper-{index}",
            "runtime_file_id": f"runtime-{index}",
            "filename": "paper.pdf",
        }
        for index in (1, 2)
    ]
    resolver = SourceIdentityResolver(records)

    assert resolver.resolve("paper.pdf") == ""
    assert resolver.resolve("paper-1") == "paper-1"
    assert resolver.ambiguous_alias_count > 0


def test_roundtrip_does_not_imply_gold_join():
    prediction: dict[str, Any] = {
        "source_identity_crosswalk": [],
        "gold_evidence": [{"document_id": "paper-gold-id", "page": 7}],
        "evidence_metadata": {
            "canonical_candidate_evidence": [
                {"source_id": "8edc-runtime-uuid", "page_label": "7"}
            ]
        },
    }

    metrics = stage_coverage_values(
        prediction,
        prediction["evidence_metadata"],
        candidates=prediction["evidence_metadata"]["canonical_candidate_evidence"],
        candidate_pool=prediction["evidence_metadata"]["canonical_candidate_evidence"],
        reranked=None,
        gold={("paper-gold-id", "7", "", "")},
    )
    assert metrics["candidate_recall_at_50"] == 0.0


def test_supported_core_with_unsupported_extension_is_revised():
    evidence = "The paper uses labeled features for the classification model."
    result = verify_qasper_answerability(
        _JsonLLM(
            {
                "verdict": "supported_with_pruning",
                "evidence_quote": evidence,
                "revised_answer": "labeled features",
            }
        ),
        question="What features does the classification model use?",
        evidence=evidence,
        candidate_answer="labeled features and an undocumented graph module",
    )

    assert result.answer == "labeled features"
    assert result.trace["action"] == "pruned_unsupported_extension"
    assert result.trace["verdict"] == "supported_with_pruning"


def test_supported_core_is_not_overwritten_by_strict_whole_answer_verifier():
    evidence = "The paper uses labeled features for the classification model."
    result = verify_qasper_answerability(
        _JsonLLM(
            {
                "verdict": "supported",
                "evidence_quote": evidence,
                "revised_answer": "",
            }
        ),
        question="What features does the classification model use?",
        evidence=evidence,
        candidate_answer="labeled features",
    )

    assert result.answer == "labeled features"
    assert result.trace["action"] == "confirmed_candidate"


def test_partial_qasper_list_recovers_grounded_atom_when_revision_is_empty():
    evidence = (
        "We address the robustness problem on top of GE-FL, a GE method which "
        "leverages labeled features as prior knowledge."
    )
    result = verify_qasper_answerability(
        _JsonLLM(
            {
                "verdict": "partially_supported",
                "evidence_quote": evidence,
                "revised_answer": "",
            }
        ),
        question="What background knowledge do they leverage?",
        evidence=evidence,
        candidate_answer=(
            "The background knowledge they leverage includes labeled features, "
            "class distribution, and neutral features. Labeled features are "
            "manually provided indicators, while neutral features prevent bias."
        ),
    )

    assert result.answer == "labeled features"
    assert result.trace["action"] == "pruned_unsupported_extension"
    assert "class distribution" not in result.answer
    assert "neutral features" not in result.answer


def test_loaded_reranker_without_execution_fails_gate():
    metadata = {
        "ranking_trace": {
            "configured": True,
            "loaded": True,
            "executed": False,
            "failure_reason": "reranker_not_called",
        }
    }
    metrics = prediction_gate_metrics(
        {
            "gold_answers": ["answer"],
            "gold_evidence": [],
            "predicted_answer": "answer",
        },
        metadata,
        candidates=[{"evidence_id": "a"}],
        reranker_input=[{"evidence_id": "a"}],
        reranked=[],
        selected=[{"evidence_id": "a"}],
        generation_context=[{"evidence_id": "a"}],
    )

    assert metrics["reranker_applicable"] == 1.0
    assert metrics["reranker_executed"] == 0.0
    assert metrics["reranker_passed"] == 0.0


def test_partial_reranker_input_materializes_with_explicit_lineage():
    candidates: list[dict[str, Any]] = [
        {
            "source_id": "paper",
            "evidence_id": "a",
            "reranker_input_identity": "evidence:paper:a",
            "reranker_score": 0.9,
            "reranker_backend": "tei",
            "reranker_model": "bge",
        },
        {"source_id": "paper", "evidence_id": "protected"},
    ]
    trace = {
        "configured": True,
        "loaded": True,
        "executed": True,
        "backend": "tei",
        "model": "bge",
        "input_count": 1,
        "output_count": 1,
        "score_field": "reranker_score",
        "input_identities": ["evidence:paper:a"],
        "output_identities": ["evidence:paper:a"],
        "failure_reason": "",
    }

    output, ranking = materialize_reranked_candidates(
        candidates,
        {"reranker_execution_trace": trace},
        limit=30,
    )

    assert [item["evidence_id"] for item in output or []] == ["a"]
    assert ranking["executed"] is True
    assert ranking["input_count"] == 1
    assert ranking["output_count"] == 1
    assert ranking["backend_output_count"] == 1
    assert ranking["reranker_artifact_record_count"] == 1


def test_reranker_trace_reports_materialized_count_after_identity_dedupe():
    candidates = [
        {
            "source_id": "paper",
            "span_id": "same",
            "reranker_input_identity": "raw:a",
            "reranker_score": 0.9,
        },
        {
            "source_id": "paper",
            "span_id": "same",
            "reranker_input_identity": "raw:b",
            "reranker_score": 0.8,
        },
    ]
    trace = {
        "configured": True,
        "loaded": True,
        "executed": True,
        "backend": "tei",
        "model": "bge",
        "input_count": 2,
        "output_count": 2,
        "score_field": "reranker_score",
        "input_identities": ["raw:a", "raw:b"],
        "output_identities": ["raw:a", "raw:b"],
    }

    output, ranking = materialize_reranked_candidates(
        candidates,
        {"reranker_execution_trace": trace},
        limit=30,
    )

    assert len(output or []) == 1
    assert ranking["backend_output_count"] == 2
    assert ranking["output_count"] == 1
    assert ranking["reranker_artifact_record_count"] == 1


def test_predicted_source_recall_is_not_citation_recall():
    metrics = core_answer_metrics(
        {
            "predicted_sources": ["paper#page:1"],
            "gold_sources": ["paper#page:1"],
        },
        predicted_answer="answer",
        gold_answers=["answer"],
        abstained=False,
        false_abstention=0.0,
        page_scores=(1.0, 1.0, 1.0),
        format_scores=(None, None),
        rewrite_skipped=False,
    )

    assert metrics["source_retrieval_recall"] == 1.0
    assert metrics["citation_recall"] is None
