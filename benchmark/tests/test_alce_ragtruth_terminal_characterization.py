from __future__ import annotations

import json
from typing import Any

from ktem.docqa.evidence_identity import identity_of

from benchmark.answer_finalizer import finalize_prediction_answer


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
