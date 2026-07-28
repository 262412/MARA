from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.controller import RetrieveDecision, build_controller_outputs
from ktem.docqa.evidence import EvidenceBundle
from ktem.docqa.verification import verify_decision


def test_strict_verifier_supports_profitability_margin_paraphrase():
    payload = build_controller_outputs(
        DocQARequest(
            prompt="What happened to profitability?",
            verification_mode="strict",
        ),
        [],
        {
            "evidence": [
                {
                    "evidence_id": "source-1",
                    "file_id": "source-1",
                    "text": "The gross margin improved.",
                }
            ]
        },
        answer="Final answer: Profitability improved.",
    )

    assert payload["verify_decision"]["status"] == "supported"
    assert payload["verify_decision"]["unsupported_claims"] == []
    assert payload["guardrail_decision"]["action"] == "return"


def test_strict_verifier_rejects_wrong_numeric_claim_with_token_overlap():
    payload = build_controller_outputs(
        DocQARequest(
            prompt="What was revenue?",
            verification_mode="strict",
        ),
        [],
        {
            "evidence": [
                {
                    "evidence_id": "revenue-cell",
                    "file_id": "report",
                    "cell_id": "revenue-2023",
                    "evidence_level": "cell",
                    "value": "100",
                    "unit": "USD",
                    "scale": "million",
                    "text": "Revenue was $100 million.",
                }
            ]
        },
        answer="Final answer: Revenue was $999 million.",
    )

    assert payload["verify_decision"]["status"] == "unsupported"
    assert payload["verify_decision"]["verified_citations"] == []


def test_strict_verifier_uses_available_evidence_before_abstaining():
    request = DocQARequest(
        prompt="What was 2024 revenue?",
        verification_mode="strict",
    )
    retrieve = RetrieveDecision(
        status="not_enough_evidence",
        reason="retrieval threshold was not met",
        retry=False,
    )
    bundle = EvidenceBundle(
        route="crag_guarded",
        items=[
            {
                "evidence_id": "source-1",
                "file_id": "source-1",
                "text": "The report says revenue increased to 42 million in 2024.",
            }
        ],
    )

    decision = verify_decision(
        request,
        retrieve,
        bundle,
        answer="Final answer: Revenue increased to 42 million in 2024.",
    )

    assert decision.status == "supported"
    assert decision.action == "generate"
    assert decision.claims == ["Revenue increased to 42 million in 2024."]


def test_two_shared_tokens_do_not_become_claim_level_support():
    request = DocQARequest(
        prompt="How was the retrieval model trained?",
        verification_mode="strict",
    )
    bundle = EvidenceBundle(
        route="doc_text",
        items=[
            {
                "evidence_id": "source-1",
                "source_id": "paper",
                "text": "The retrieval model improves precision.",
            }
        ],
    )

    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="ok"),
        bundle,
        answer="The retrieval model was trained on Wikipedia.",
    )

    assert decision.status == "unknown"
    assert decision.unsupported_claims == []
    assert decision.unknown_claims == ["The retrieval model was trained on Wikipedia."]
    assert decision.verified_citations == []
    assert decision.claim_results == [
        {
            "claim_id": "claim:1",
            "claim": "The retrieval model was trained on Wikipedia.",
            "status": "unknown",
            "supporting_evidence_ids": [],
            "contradicting_evidence_ids": [],
        }
    ]
