from ktem.docqa.controller import evaluate_retrieval_quality


def test_evaluate_retrieval_quality_does_not_apply_finance_rules_by_default():
    decision = evaluate_retrieval_quality(
        "doc_text",
        {
            "evidence": [
                {
                    "evidence_id": "doc-1",
                    "file_id": "paper",
                    "page_label": "3",
                    "text": "The paper discusses capital intensive manufacturing.",
                }
            ]
        },
        prompt=(
            "Which segment is more capital-intensive based on net sales and "
            "total assets?"
        ),
    )

    assert decision.status == "good"
    assert decision.reason == "Retrieved evidence is sufficient for generation."


def test_evaluate_retrieval_quality_applies_finance_rules_when_opted_in():
    decision = evaluate_retrieval_quality(
        "doc_text",
        {
            "evidence": [
                {
                    "evidence_id": "doc-1",
                    "file_id": "filing",
                    "page_label": "3",
                    "text": "The filing discusses capital intensive manufacturing.",
                }
            ]
        },
        prompt=(
            "Which segment is more capital-intensive based on net sales and "
            "total assets?"
        ),
        verification_domain="finance",
    )

    assert decision.status == "ambiguous"
    assert "financial statement fields" in decision.reason


def test_segment_proportional_change_requires_segment_sales_table():
    prompt = (
        "From FY21 to FY22, excluding Embedded, in which AMD reporting "
        "segment did sales proportionally increase the most?"
    )
    missing = evaluate_retrieval_quality(
        "doc_text",
        {
            "evidence": [
                {
                    "evidence_id": "company-overview",
                    "file_id": "filing",
                    "page_label": "3",
                    "text": "AMD reports Data Center, Client, Gaming, and Embedded.",
                }
            ]
        },
        prompt=prompt,
        verification_domain="finance",
    )
    sufficient = evaluate_retrieval_quality(
        "doc_text",
        {
            "evidence": [
                {
                    "evidence_id": "segment-table",
                    "file_id": "filing",
                    "page_label": "47",
                    "text": (
                        "Reporting Segment. Net revenue by segment. "
                        "2022 2021. Data Center 6,043 3,694; "
                        "Client 6,201 6,887; Gaming 6,805 5,607."
                    ),
                }
            ]
        },
        prompt=prompt,
        verification_domain="finance",
    )

    assert missing.status == "ambiguous"
    assert "financial statement fields" in missing.reason
    assert sufficient.status == "good"
