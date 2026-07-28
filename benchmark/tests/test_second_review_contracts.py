from types import SimpleNamespace
from typing import Any

from ktem.docqa.evidence_identity import identity_of

from benchmark.answer_finalizer import finalize_prediction_answer
from benchmark.citation_stage_projection import record_emitted_citation_evidence
from benchmark.contract_invariant_metrics import contract_invariant_summary
from benchmark.repair_plan import evaluate_release_gates
from benchmark.report_identity_compaction import compact_identity_evidence_list
from benchmark.stage_metrics import prediction_stage_metrics
from benchmark.summary import add_mara_summary_fields
from benchmark.task_answer_contracts import apply_task_answer_contract


class _QasperVerifier:
    def __call__(self, _prompt: str, **_kwargs):
        return SimpleNamespace(
            text='{"verdict":"insufficient_evidence","evidence_quote":""}'
        )


def test_canonical_source_alias_records_emitted_citation_evidence():
    candidate = {
        "evidence_id": "runtime-hit",
        "source_id": "runtime-report",
        "source_aliases": ["canonical-report"],
        "page_label": "5",
        "text": "The answer.",
    }
    prediction: dict[str, Any] = {"evidence_metadata": {}}

    record_emitted_citation_evidence(
        prediction,
        citations=[{"source_id": "canonical-report", "page_label": "5"}],
        candidates=[candidate],
    )

    assert prediction["evidence_metadata"]["emitted_citation_evidence"]


def test_page_citation_provenance_accepts_canonical_backref():
    candidate = {
        "source_id": "runtime-report",
        "page_label": "3",
        "source_aliases": ["canonical-report"],
        "page_aliases": ["3", "5"],
        "source_backrefs": ["canonical-report#page:5"],
        "text": "The answer.",
    }
    cited = {
        "source_id": "canonical-report",
        "page_label": "5",
        "evidence_level": "page",
    }

    summary = contract_invariant_summary(
        [
            {
                "evidence_metadata": {
                    "canonical_candidate_evidence": [candidate],
                    "emitted_citation_evidence": [cited],
                }
            }
        ]
    )

    assert summary["citation_provenance_violation_count"] == 0.0


def test_calculation_citations_union_explanatory_claim_citations():
    operand = {
        "evidence_id": "operand",
        "source_id": "report",
        "page_label": "4",
        "text": "Revenue was 100 and later 120.",
    }
    explanation = {
        "evidence_id": "explanation",
        "source_id": "report",
        "page_label": "9",
        "text": "Management attributed growth to higher demand.",
    }
    prediction: dict[str, Any] = {
        "predicted_answer": (
            "The percentage change was 20%. "
            "Management attributed this to higher demand."
        ),
        "answer_type": "numeric",
        "gold_evidence": [{"source_id": "report", "page_label": "4"}],
        "evidence_bundle": {
            "items": [operand, explanation],
            "metadata": {
                "verified_claim_support_by_claim": {
                    "claim:2": [identity_of(explanation).key],
                },
                "finance_numeric_trace": {
                    "calculation_execution": {
                        "status": "ok",
                        "citation_ids": ["operand"],
                    }
                },
            },
        },
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="financebench",
        mode="scoring_adapter_v1",
    )

    assert {
        (citation["source_id"], citation["page_label"])
        for citation in prediction["structured_citations"]
    } == {("report", "4"), ("report", "9")}


def test_qasper_answer_change_clears_top_level_verifier_state():
    prediction: dict[str, Any] = {
        "question": "Did the authors release the code?",
        "predicted_answer": "yes",
        "answer_for_scoring": "yes",
        "answer_type": "boolean",
        "verify_decision": {"status": "supported"},
        "claim_verification": {"status": "supported"},
        "guardrail_decision": {"status": "ok"},
        "verifier_observability": {"has_unsupported_claim": 0},
        "evidence_metadata": {},
    }

    apply_task_answer_contract(
        prediction,
        dataset_name="qasper",
        llm_factory=_QasperVerifier,
    )

    assert prediction["verify_decision"]["status"] != "supported"
    for key in ("guardrail_decision", "verifier_observability"):
        assert key not in prediction
    assert prediction["pre_contract_verification"]["verify_decision"] == {
        "status": "supported"
    }


def test_qasper_answer_change_runs_post_contract_verification():
    prediction: dict[str, Any] = {
        "question": "Did the authors release the code?",
        "predicted_answer": "yes",
        "answer_for_scoring": "yes",
        "answer_type": "boolean",
        "evidence_metadata": {
            "evidence": [
                {
                    "source_id": "paper",
                    "span_id": "statement",
                    "text": "The paper does not resolve whether code was released.",
                }
            ]
        },
    }

    apply_task_answer_contract(
        prediction,
        dataset_name="qasper",
        llm_factory=_QasperVerifier,
    )

    post = prediction["post_contract_verification"]
    assert post["answer"] == "unanswerable"
    assert post["status"] == "not_enough_evidence"
    assert prediction["verify_decision"] == post["verify_decision"]


def test_duplicate_identity_contract_gate_detects_duplicate_atoms():
    shared = {
        "source_id": "report",
        "cell_id": "revenue",
        "period": "2023",
    }
    summary = contract_invariant_summary(
        [
            {
                "evidence_metadata": {
                    "canonical_candidate_evidence": [
                        {**shared, "value": "100", "text": "Revenue 100"},
                        {**shared, "value": "120", "text": "Revenue 120"},
                    ]
                }
            }
        ]
    )

    assert summary["duplicate_identity_count"] == 1.0
    assert summary["conflicting_identity_count"] == 1.0


def test_roundtrip_contract_reports_each_projection_dimension():
    item = {
        "runtime_source_id": "runtime-report",
        "source_aliases": ["canonical-report"],
        "page_label": "3",
        "dataset_page": "5",
        "page_aliases": ["3", "5"],
        "cell_id": "revenue",
        "evidence_level": "cell",
        "bbox": [1, 2, 3, 4],
        "retrieval_lineage": [{"retriever_name": "dense"}],
        "representations": [{"modality": "ocr", "text": "Revenue 120"}],
        "ocr_text": "Revenue 120",
        "vlm_text": "A table cell",
        "continuation_id": "table-pages-3-4",
        "neighbor_element_ids": ["revenue-prior"],
        "text": "Revenue 120",
    }

    summary = contract_invariant_summary(
        [{"evidence_metadata": {"canonical_candidate_evidence": [item]}}]
    )

    assert summary["atomic_field_roundtrip_rate"] == 1.0
    assert summary["locator_roundtrip_rate"] == 1.0
    assert summary["lineage_roundtrip_rate"] == 1.0
    assert summary["representation_roundtrip_rate"] == 1.0


def test_canonical_candidate_and_reranker_input_metrics_are_distinct():
    gold = {
        "source_id": "paper",
        "page_label": "9",
        "span_id": "gold",
        "text": "Gold evidence.",
    }
    prediction = {
        "gold_evidence": [gold],
        "evidence_metadata": {
            "canonical_candidate_evidence": [gold],
            "candidate_ranked_evidence": [gold],
            "fused_evidence": [gold],
            "reranker_input_evidence": [
                {
                    "source_id": "paper",
                    "page_label": "4",
                    "span_id": "other",
                    "text": "Other evidence.",
                }
            ],
        },
    }

    metrics = prediction_stage_metrics(prediction)

    assert metrics["canonical_candidate_evidence_coverage"] == 1.0
    assert metrics["reranker_input_evidence_coverage"] == 0.0


def test_standard_summary_emits_per_example_metric_records():
    prediction = {
        "example_id": "ex-1",
        "route": "controller",
        "benchmark_role": "qa_quality",
        "metrics": {"native_score": 0.75, "f1": 0.5},
        "error": None,
    }

    summary = add_mara_summary_fields({"dataset_name": "qasper"}, [prediction])

    assert summary["per_example_metric_records"] == [
        {
            "dataset": "qasper",
            "example_id": "ex-1",
            "route": "controller",
            "deployed_policy": "",
            "primary_score": 0.75,
            "metrics": {"native_score": 0.75, "f1": 0.5},
            "error": None,
            "error_type": "",
            "timed_out": False,
        }
    ]


def test_paired_gate_fails_when_paired_example_count_is_zero():
    results = evaluate_release_gates(
        phase_b={"primary_score": 0.5},
        phase_g={"primary_score": 0.6},
        paired_semantic_ci_low=None,
    )

    gate = results["deployed_native_score_delta"]
    assert gate["value"] is None
    assert gate["paired_example_count"] == 0
    assert gate["status"] == "missing"
    assert gate["passed"] is False


def test_compact_artifact_preserves_fact_audit_fields():
    item = {
        "source_id": "paper",
        "runtime_source_id": "runtime-paper",
        "page_number": 7,
        "figure_label": "Figure 2",
        "table_label": "Table 4",
        "cell_id": "revenue",
        "parent_element_id": "table-4",
        "neighbor_element_ids": ["cell-cost"],
        "section_id": "results",
        "value": "120",
        "period_kind": "fiscal_year",
        "statement_kind": "income_statement",
        "financial_scope": "consolidated",
        "bbox": [1, 2, 3, 4],
        "caption": "Revenue table",
        "ocr_text": "Revenue 120",
        "vlm_text": "A revenue row",
        "chunk_start": 10,
        "chunk_end": 21,
    }

    projected_items = compact_identity_evidence_list([item], "candidate_evidence")
    assert projected_items is not None
    [projected] = projected_items

    for field, value in item.items():
        assert projected[field] == value
