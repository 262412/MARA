from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.execution import execute_controller_turn

from benchmark.answer_finalizer import finalize_prediction_answer
from benchmark.contract_invariant_metrics import contract_invariant_summary
from benchmark.task_answer_contracts import synchronize_terminal_answer_state


def _prediction_with_verified_claim(answer: str) -> dict[str, Any]:
    item = {
        "evidence_id": "revenue-evidence",
        "source_id": "report",
        "page_label": "5",
        "text": "Revenue increased.",
    }
    evidence_id = identity_of(item).key
    return {
        "predicted_answer": answer,
        "answer_type": "citation_qa",
        "gold_evidence": [{"source_id": "report", "page_label": "5"}],
        "verify_decision": {
            "status": "supported",
            "claim_results": [
                {
                    "claim_id": "claim:1",
                    "claim": "Revenue increased.",
                    "status": "supported",
                    "supporting_evidence_ids": [evidence_id],
                }
            ],
        },
        "evidence_bundle": {"items": [item], "metadata": {}},
        "evidence_metadata": {},
    }


def _runtime_prediction(answer: str, item: dict[str, Any]) -> dict[str, Any]:
    execution = execute_controller_turn(
        DocQARequest(
            prompt="Who is identified by the source?",
            retrieval_query="Who is identified by the source?",
            task_type="free_text",
            verification_domain="general",
            verification_mode="off",
            route_policy="doc",
            allowed_routes=["doc_text"],
            selected_file_ids=[str(item["source_id"])],
            origin="benchmark",
        ),
        retrieve=lambda *_args: {"evidence": [item]},
        generate=lambda *_args: answer,
    )
    prediction = {
        **execution.as_dict(),
        "question": "Who is identified by the source?",
        "answer_type": "free_text",
        "predicted_answer": execution.answer,
        "route": "text_rag",
        "gold_answers": [answer],
        "gold_evidence": [{"source_id": item["source_id"]}],
        "evidence_metadata": deepcopy(execution.evidence_bundle.metadata),
        "structured_citations": [],
        "predicted_citations": [],
    }
    return prediction


def test_alce_text_controller_finalizer_projects_verified_claim_to_emitted_citation():
    prediction = _prediction_with_verified_claim("Revenue increased.")

    finalize_prediction_answer(
        prediction,
        dataset_name="alce-asqa",
        mode="scoring_adapter_v1",
    )

    assert prediction["answer_for_scoring"] == "Revenue increased"
    assert prediction["structured_citations"]
    for metadata in (
        prediction["evidence_bundle"]["metadata"],
        prediction["evidence_metadata"],
    ):
        assert metadata["emitted_citation_evidence"]
        assert metadata["cited_evidence"] == metadata["emitted_citation_evidence"]
        assert metadata["citation_stage_contract"] == "emitted_citation_evidence.v1"


def test_ragtruth_keeps_exact_json_and_records_citations_out_of_band():
    answer = '{"hallucination list": ["profit doubled"]}'
    prediction = _prediction_with_verified_claim("Revenue increased.")
    prediction["predicted_answer"] = answer
    prediction["answer_type"] = "verification"

    finalize_prediction_answer(
        prediction,
        dataset_name="ragtruth-plan5",
        mode="scoring_adapter_v1",
    )

    assert prediction["answer_for_user"] == answer
    assert prediction["answer_for_scoring"] == answer
    assert json.loads(prediction["answer_for_scoring"]) == {
        "hallucination list": ["profit doubled"]
    }
    assert prediction["answer_finalization"]["source"] == "ragtruth_contract"
    assert prediction["structured_citations"]
    assert "citations" not in json.loads(prediction["answer_for_scoring"])
    assert prediction["evidence_metadata"]["emitted_citation_evidence"]


def test_alce_adapter_authority_survives_runtime_terminal_synchronization():
    item = {
        "evidence_id": "music-span",
        "source_id": "report",
        "text": "The performers were Simon & Garfunkel.",
    }
    prediction = _runtime_prediction("Simon & Garfunkel", item)
    trace = {
        "contract_id": "alce_short_answer_grounding.v2",
        "status": "ok",
        "verdict": "supported",
        "evidence_id": "music-span",
        "grounded_answer": "Simon & Garfunkel",
        "answer_changed": False,
    }
    prediction["evidence_metadata"]["alce_answer_grounding"] = trace
    prediction["evidence_bundle"]["metadata"]["alce_answer_grounding"] = trace

    finalize_prediction_answer(
        prediction,
        dataset_name="alce-asqa",
        mode="scoring_adapter_v1",
    )
    assert synchronize_terminal_answer_state(prediction)

    identity = identity_of(item).key
    assert prediction["benchmark_adapter_authority_commit"]["contract_id"] == (
        "benchmark_adapter_authority_commit.v1"
    )
    assert [
        identity_of(value).key
        for value in prediction["terminal_answer_state"]["supporting_evidence"]
    ] == [identity]
    assert prediction["verify_decision"]["status"] == "supported"
    assert prediction["evidence_metadata"]["emitted_citation_evidence"]


def test_ragtruth_adapter_authority_survives_runtime_terminal_synchronization():
    answer = '{"hallucination list": []}'
    item = {
        "evidence_id": "source-span",
        "source_id": "report",
        "text": "Alice won the race.",
    }
    prediction = _runtime_prediction(answer, item)
    metadata = {
        "ragtruth_claims": ["Alice won the race."],
        "ragtruth_supported_claim_indices": [0],
        "ragtruth_emitted_claim_indices": [],
        "ragtruth_source_evidence_id": identity_of(item).key,
    }
    prediction["evidence_metadata"].update(metadata)
    prediction["evidence_bundle"]["metadata"].update(metadata)

    finalize_prediction_answer(
        prediction,
        dataset_name="ragtruth-plan5",
        mode="scoring_adapter_v1",
    )
    assert synchronize_terminal_answer_state(prediction)

    assert prediction["predicted_answer"] == answer
    assert prediction["answer_for_scoring"] == answer
    assert prediction["verify_decision"]["status"] == "supported"
    assert len(prediction["terminal_answer_state"]["supporting_evidence"]) == 1
    assert prediction["evidence_metadata"]["emitted_citation_evidence"]


def test_structured_citation_without_verified_canonical_support_fails_gate():
    prediction = {
        "question": "What happened?",
        "answer_type": "free_text",
        "predicted_answer": "Revenue increased.",
        "answer_for_scoring": "Revenue increased.",
        "answer_status": "answered",
        "route": "text_rag",
        "gold_answers": ["Revenue increased."],
        "gold_evidence": [{"source_id": "report", "page_label": "5"}],
        "structured_citations": [{"source_id": "report", "page_label": "5"}],
        "evidence_metadata": {
            "candidate_evidence": [],
            "selected_evidence": [],
            "generation_context_evidence": [],
            "verified_claim_support_evidence": [],
            "emitted_citation_evidence": [],
        },
    }

    summary = contract_invariant_summary([prediction])

    assert summary["required_citation_missing_count"] == 1.0
    assert summary["verified_claim_support_coverage"] == 0.0
    assert summary["contract_gates"]["citation_emission"]["status"] == "failed"
