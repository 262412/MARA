import json
from types import SimpleNamespace
from typing import Any

from benchmark.answer_finalizer import (
    attach_structured_citations_from_evidence,
    finalize_prediction_answer,
)
from benchmark.citation_stage_projection import (
    _citation_matches_item,
    record_emitted_citation_evidence,
)
from benchmark.docqa_evidence_projection import evidence_element_ids
from benchmark.evidence_identity_metrics import reranker_lineage
from benchmark.headline_policy import headline_policy_predictions
from benchmark.page_stage_metrics import all_gold_pages_hit, stage_all_gold_pages_hit
from benchmark.performance_timing import runtime_timing_payload
from benchmark.qasper_answerability import verify_qasper_answerability
from benchmark.repair_plan import JUDGE_CALIBRATION_GATES, PAIRED_REGRESSION_GATES
from benchmark.stage_metrics import prediction_stage_metrics
from benchmark.summary import _primary_score_summary
from benchmark.task_answer_contracts import apply_task_answer_contract


class _VerifierLLM:
    def __init__(self, response: str):
        self.response = response

    def __call__(self, _prompt: str, **_kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(text=self.response)


def _cell(source: str, page: str, cell_id: str, value: str) -> dict[str, str]:
    return {
        "evidence_id": "table-1",
        "source_id": source,
        "page_label": page,
        "cell_id": cell_id,
        "evidence_level": "cell",
        "text": value,
    }


def test_evidence_id_does_not_bypass_source_page_constraints():
    item = _cell("document-a", "5", "revenue-2023", "Revenue was 12.")

    assert not _citation_matches_item(
        {
            "evidence_id": "revenue-2023",
            "source_id": "document-b",
            "page_label": "8",
        },
        item,
    )


def test_page_citation_does_not_expand_to_all_atomic_evidence():
    prediction: dict[str, Any] = {"evidence_metadata": {}}
    candidates = [
        _cell("report", "5", "revenue-2022", "Revenue was 10."),
        _cell("report", "5", "revenue-2023", "Revenue was 12."),
    ]

    record_emitted_citation_evidence(
        prediction,
        citations=[
            {
                "kind": "page",
                "source_id": "report",
                "page_label": "5",
            }
        ],
        candidates=candidates,
    )

    cited = prediction["evidence_metadata"]["cited_evidence"]
    assert len(cited) == 1
    assert cited[0]["evidence_level"] == "page"
    assert cited[0]["source_id"] == "report"
    assert cited[0]["page_label"] == "5"
    assert "cell_id" not in cited[0]


def test_generic_citation_requires_verified_claim_support():
    unsupported: dict[str, Any] = {
        "evidence_bundle": {
            "items": [
                {
                    "evidence_id": "candidate-1",
                    "source_id": "paper",
                    "page_label": "2",
                    "text": "Only a retrieved candidate.",
                }
            ],
            "metadata": {},
        },
        "evidence_metadata": {},
    }
    supported: dict[str, Any] = {
        "evidence_bundle": {
            "items": list(unsupported["evidence_bundle"]["items"]),
            "metadata": {
                "verified_claim_support_evidence": list(
                    unsupported["evidence_bundle"]["items"]
                )
            },
        },
        "evidence_metadata": {},
    }

    assert attach_structured_citations_from_evidence(unsupported, span="answer") == []
    citations = attach_structured_citations_from_evidence(supported, span="answer")
    assert len(citations) == 1
    assert citations[0]["evidence_id"] == "evidence:paper:candidate-1"


def test_reranker_lineage_rejects_same_local_id_from_different_source():
    candidate = _cell("document-a", "5", "revenue-2023", "Revenue was 12.")
    reranked = _cell("document-b", "5", "revenue-2023", "Revenue was 12.")

    coverage, violations = reranker_lineage([candidate], [reranked])

    assert coverage == 0.0
    assert violations == 1


def test_reranker_lineage_uses_actual_reranker_input():
    restored = {
        "evidence_id": "required",
        "source_id": "paper",
        "page_label": "9",
        "text": "Required evidence.",
    }
    prediction = {
        "gold_evidence": [
            {
                "source_id": "paper",
                "page_label": "9",
                "evidence_id": "required",
            }
        ],
        "evidence_metadata": {
            "candidate_evidence": [
                {
                    "evidence_id": f"candidate-{index}",
                    "source_id": "paper",
                    "page_label": "1",
                    "text": f"Candidate {index}",
                }
                for index in range(80)
            ]
            + [restored],
            "candidate_ranked_evidence": [restored],
            "reranker_input_evidence": [restored],
            "reranked_evidence": [restored],
            "ranking_trace": {"backend_execution": True},
        },
    }

    metrics = prediction_stage_metrics(prediction)

    assert metrics["reranker_lineage_coverage"] == 1.0


def test_all_gold_pages_hit_ignores_candidate_only_pages():
    prediction = {
        "gold_evidence": [{"source_id": "paper", "page_label": "9"}],
        "evidence_metadata": {
            "candidate_evidence": [{"source_id": "paper", "page_label": "9"}],
            "selected_evidence": [{"source_id": "paper", "page_label": "4"}],
            "generation_context_evidence": [{"source_id": "paper", "page_label": "4"}],
        },
    }

    assert stage_all_gold_pages_hit(prediction, "candidate_evidence") == 1.0
    assert stage_all_gold_pages_hit(prediction, "selected_evidence") == 0.0
    assert all_gold_pages_hit(prediction) == 0.0


def test_span_id_precedes_parent_element_id_projection():
    assert evidence_element_ids(
        [
            {
                "source_id": "paper",
                "span_id": "supporting-span",
                "element_id": "paragraph-12",
            }
        ]
    ) == ["supporting-span"]


def test_qasper_boolean_conflict_does_not_preserve_wrong_answer():
    llm = _VerifierLLM(
        '{"verdict":"yes_complete","evidence_quote":'
        '"The authors released their source code with the paper."}'
    )

    result = verify_qasper_answerability(
        llm,
        question="Did the authors release the code?",
        evidence="The authors released their source code with the paper.",
        candidate_answer="no",
    )

    assert result.answer == "yes"
    assert result.trace["action"] == "corrected_polarity"


def test_task_contract_recomputes_citations_after_answer_change():
    llm = _VerifierLLM('{"verdict":"insufficient_evidence","evidence_quote":""}')
    prediction: dict[str, Any] = {
        "question": "Did the authors release the code?",
        "predicted_answer": "yes",
        "answer_for_scoring": "yes",
        "answer_type": "boolean",
        "structured_citations": [
            {
                "kind": "element",
                "evidence_id": "element:paper:old",
                "source_id": "paper",
                "page_label": "2",
            }
        ],
        "predicted_citations": ["paper#page:2"],
        "evidence_metadata": {
            "verified_claim_support_evidence": [
                {
                    "evidence_id": "old",
                    "source_id": "paper",
                    "page_label": "2",
                }
            ]
        },
        "context_preview": "The paper does not resolve this proposition.",
    }

    changed = apply_task_answer_contract(
        prediction,
        dataset_name="qasper",
        llm_factory=lambda: llm,
    )
    finalize_prediction_answer(
        prediction,
        dataset_name="qasper",
        mode="scoring_adapter_v1",
    )

    assert changed is True
    assert prediction["predicted_answer"] == "unanswerable"
    assert prediction["structured_citations"] == []
    assert prediction["predicted_citations"] == []
    assert prediction["evidence_metadata"]["cited_evidence"] == []


def test_headline_policy_uses_manifest_role_instead_of_route_name():
    predictions = [
        {
            "route": "mara_thorough",
            "headline_role": "deployed_policy",
        },
        {
            "route": "controller_auto",
            "headline_role": "diagnostic",
        },
    ]

    selected, policy = headline_policy_predictions(predictions)

    assert selected == [predictions[0]]
    assert policy == "deployed_manifest_policy"


def test_manifest_deployed_policy_uses_deployed_headline_metric():
    summary = _primary_score_summary(
        [
            {
                "route": "mara_thorough",
                "benchmark_role": "qa_quality",
                "headline_role": "deployed_policy",
                "metrics": {"native_score": 0.8},
            },
            {
                "route": "controller_auto",
                "benchmark_role": "qa_quality",
                "headline_role": "diagnostic",
                "metrics": {"native_score": 0.9},
            },
        ]
    )

    assert summary["primary_score_metric"] == "deployed_policy_avg_native_score"
    assert summary["primary_score"] == 0.8


def test_release_gates_separate_judge_calibration_and_core_regressions():
    assert {gate.category for gate in JUDGE_CALIBRATION_GATES} == {"judge_calibration"}
    paired_metrics = {gate.metric for gate in PAIRED_REGRESSION_GATES}
    assert {
        "deployed_native_score_delta",
        "false_abstention_delta",
        "citation_score_delta",
        "execution_error_delta",
    } <= paired_metrics


def test_page_citation_round_trip_keeps_explicit_granularity():
    prediction: dict[str, Any] = {
        "predicted_answer": json.dumps(
            {
                "answer": "The result is on page five.",
                "citations": [
                    {
                        "kind": "page",
                        "source_id": "report",
                        "page_label": "5",
                    }
                ],
            }
        ),
        "evidence_bundle": {
            "items": [_cell("report", "5", "value", "The result.")],
            "metadata": {},
        },
        "evidence_metadata": {},
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="alce",
        mode="scoring_adapter_v1",
    )

    assert prediction["structured_citations"][0]["kind"] == "page"
    assert (
        prediction["evidence_metadata"]["cited_evidence"][0]["evidence_level"] == "page"
    )


def test_stage_coverage_identity_includes_evidence_kind():
    prediction = {
        "gold_evidence": [
            {
                "source_id": "paper",
                "page_label": "2",
                "cell_id": "shared-local-id",
            }
        ],
        "evidence_metadata": {
            "candidate_evidence": [
                {
                    "source_id": "paper",
                    "page_label": "2",
                    "span_id": "shared-local-id",
                    "evidence_level": "span",
                }
            ]
        },
    }

    metrics = prediction_stage_metrics(prediction)

    assert metrics["candidate_recall_at_50"] == 0.0


def test_runtime_turn_timing_is_not_reported_as_generation():
    timings, performance = runtime_timing_payload(
        {
            "pipeline_stage_timings": {
                "planning_seconds": 1.0,
                "retrieval_seconds": 2.0,
                "generation_seconds": 3.0,
                "verification_seconds": 4.0,
            }
        },
        index_seconds=0.5,
        runtime_turn_seconds=10.0,
        grounding_seconds=0.25,
    )

    assert timings["runtime_turn_seconds"] == 10.0
    assert timings["generation_seconds"] == 3.0
    assert performance["total_seconds"] == 10.75
