import pytest
from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.controller import build_controller_outputs
from ktem.docqa.execution import execute_controller_turn


@pytest.mark.parametrize(
    ("prompt", "answer_type"),
    [
        ("What was the percentage change from 2021 to 2022?", "numeric"),
        ("Compare the table across pages.", "free_text"),
        ("What does the chart show?", "free_text"),
    ],
)
def test_auto_policy_routes_high_risk_questions_to_hybrid(prompt, answer_type):
    payload = build_controller_outputs(
        DocQARequest(
            prompt=prompt,
            task_type=answer_type,
            route_policy="auto",
        ),
        [],
        {
            "evidence": [
                {
                    "evidence_id": "evidence-1",
                    "file_id": "file-1",
                    "page_label": "2",
                    "text": prompt,
                }
            ]
        },
    )

    assert payload["route_decision"]["route"] == "hybrid"
    assert "risk" in payload["route_decision"]["reason"].lower()


def test_second_round_targets_only_missing_evidence_slot():
    queries = []

    def retrieve(request, _decision):
        queries.append(request.retrieval_query)
        if len(queries) == 1:
            return {
                "evidence": [
                    {
                        "evidence_id": "revenue-2021",
                        "file_id": "file-1",
                        "page_label": "4",
                        "text": "Revenue was $10 million in 2021.",
                    }
                ]
            }
        return {
            "evidence": [
                {
                    "evidence_id": "revenue-2022",
                    "file_id": "file-1",
                    "page_label": "5",
                    "text": "Revenue was $12 million in 2022.",
                }
            ]
        }

    def generate(_request, _decision, bundle):
        assert {item["evidence_id"] for item in bundle.items} == {
            "revenue-2021",
            "revenue-2022",
        }
        return "20%."

    result = execute_controller_turn(
        DocQARequest(
            prompt="What was the percentage change in revenue from 2021 to 2022?",
            retrieval_query="percentage change revenue 2021 2022",
            task_type="numeric",
            verification_domain="finance",
            route_policy="doc",
        ),
        retrieve=retrieve,
        generate=generate,
    )

    assert len(queries) == 2
    assert queries[1] == "revenue 2022"
    assert result.evidence_bundle.metadata["retrieval_rounds"] == 2
    assert result.evidence_bundle.metadata["slot_coverage"] == 1.0
