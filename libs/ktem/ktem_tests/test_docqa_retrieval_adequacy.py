from ktem.docqa.controller import evaluate_retrieval_quality


def test_retrieval_evaluator_requires_capex_cash_flow_fields():
    decision = evaluate_retrieval_quality(
        "doc_text",
        {
            "evidence": [
                {
                    "evidence_id": "wrong-page",
                    "page_label": "12",
                    "text": "Net sales increased due to demand in several markets.",
                }
            ],
            "modality_counts": {"text": 1},
        },
        prompt=(
            "What is the FY2018 capital expenditure amount for 3M? "
            "Use the cash flow statement."
        ),
    )

    assert decision.status == "ambiguous"
    assert "capital expenditures" in decision.reason
    assert decision.retry is True


def test_retrieval_evaluator_accepts_capex_cash_flow_fields_with_page_support():
    decision = evaluate_retrieval_quality(
        "doc_text",
        {
            "evidence": [
                {
                    "evidence_id": "cash-flow-page",
                    "page_label": "59",
                    "text": (
                        "Consolidated Statement of Cash Flows. "
                        "Purchases of property, plant and equipment were $1,577."
                    ),
                }
            ],
            "modality_counts": {"text": 1},
        },
        prompt=(
            "What is the FY2018 capital expenditure amount for 3M? "
            "Use the cash flow statement."
        ),
    )

    assert decision.status == "good"
    assert decision.retry is False


def test_retrieval_evaluator_requires_net_ar_balance_sheet_fields():
    decision = evaluate_retrieval_quality(
        "doc_text",
        {
            "evidence": [
                {
                    "evidence_id": "legal-definition-page",
                    "page_label": "146",
                    "text": (
                        "Unless the context clearly requires, any reference to "
                        "a subsidiary is a reference to a subsidiary guarantor."
                    ),
                }
            ],
            "modality_counts": {"text": 1},
        },
        prompt=(
            "What is Amcor's year end FY2020 net AR? Use only the details "
            "shown within the balance sheet."
        ),
    )

    assert decision.status == "ambiguous"
    assert "balance sheet" in decision.reason
    assert "receivables" in decision.reason
    assert decision.retry is True


def test_retrieval_evaluator_requires_primary_customer_fields():
    decision = evaluate_retrieval_quality(
        "doc_text",
        {
            "evidence": [
                {
                    "evidence_id": "backlog-page",
                    "page_label": "41",
                    "text": (
                        "Backlog decreased primarily due to revenue recognized "
                        "on contracts awarded in prior years."
                    ),
                }
            ],
            "modality_counts": {"text": 1},
        },
        prompt="Who are the primary customers of Boeing as of FY2022?",
    )

    assert decision.status == "ambiguous"
    assert "commercial airlines" in decision.reason
    assert "U.S. government" in decision.reason
    assert decision.retry is True


def test_retrieval_evaluator_requires_geography_table_fields():
    decision = evaluate_retrieval_quality(
        "doc_text",
        {
            "evidence": [
                {
                    "evidence_id": "segment-mdna-page",
                    "page_label": "64",
                    "text": (
                        "Corporate and Other pretax loss changed due to "
                        "changes in share-based compensation and other items."
                    ),
                }
            ],
            "modality_counts": {"text": 1},
        },
        prompt=(
            "What are the geographies that American Express primarily "
            "operates in as of 2022?"
        ),
    )

    assert decision.status == "ambiguous"
    assert "geographic regions" in decision.reason
    assert "EMEA" in decision.reason
    assert decision.retry is True


def test_retrieval_evaluator_requires_dpo_statement_fields():
    decision = evaluate_retrieval_quality(
        "doc_text",
        {
            "evidence": [
                {
                    "evidence_id": "roi-page",
                    "page_label": "40",
                    "text": (
                        "The calculation of ROA and ROI reconciles ROI to the "
                        "most comparable GAAP financial measure."
                    ),
                }
            ],
            "modality_counts": {"text": 1},
        },
        prompt=(
            "What is FY2018 days payable outstanding (DPO) for Walmart? "
            "Use the statement of financial position and the P&L statement."
        ),
    )

    assert decision.status == "ambiguous"
    assert "accounts payable" in decision.reason
    assert "cost of sales" in decision.reason
    assert "inventories" in decision.reason
    assert decision.retry is True
