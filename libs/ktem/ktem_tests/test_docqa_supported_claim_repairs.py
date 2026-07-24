from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.claim_filtering import answer_claims
from ktem.docqa.controller import build_controller_outputs
from ktem.docqa.execution import execute_controller_turn


def test_answer_claims_keep_place_abbreviation_together():
    answer = (
        "Rick Kriseman won the 2017 mayor race in St. Petersburg, Florida. "
        "He defeated Rick Baker."
    )

    assert answer_claims(answer) == [
        "Rick Kriseman won the 2017 mayor race in St. Petersburg, Florida.",
        "He defeated Rick Baker.",
    ]


def test_strict_verifier_prefers_direct_support_over_irrelevant_year_conflict():
    payload = build_controller_outputs(
        DocQARequest(
            prompt="When did morning TV on TV-am start in the UK?",
            verification_mode="strict",
        ),
        [],
        {
            "evidence": [
                {
                    "evidence_id": "support",
                    "file_id": "source-1",
                    "text": (
                        "TV-am launched its morning programme in the UK on "
                        "1 February 1983."
                    ),
                },
                {
                    "evidence_id": "irrelevant",
                    "file_id": "source-1",
                    "text": (
                        "A different morning programme changed its format in 2014."
                    ),
                },
            ]
        },
        answer=(
            "Final answer: The morning TV programme on TV-am in the UK started "
            "on 1 February 1983."
        ),
    )

    assert payload["verify_decision"]["status"] == "supported"
    assert payload["guardrail_decision"]["action"] == "return"


def test_execute_controller_turn_keeps_supported_claims_without_rewrite_generator():
    def retrieve(_request, _decision):
        return {
            "evidence": [
                {
                    "evidence_id": "source-1",
                    "file_id": "source-1",
                    "text": "Rick Kriseman won the 2017 mayoral election.",
                }
            ]
        }

    def generate(_request, _decision, _bundle):
        return (
            "Rick Kriseman won the 2017 mayoral election. "
            "The election was held in 2019."
        )

    result = execute_controller_turn(
        DocQARequest(
            prompt="Who won the 2017 mayoral election?",
            route_policy="doc",
            verification_mode="strict",
        ),
        retrieve=retrieve,
        generate=generate,
    )

    assert result.verify_decision.status == "supported"
    assert result.guardrail_decision.action == "return"
    assert result.answer == "Rick Kriseman won the 2017 mayoral election."
