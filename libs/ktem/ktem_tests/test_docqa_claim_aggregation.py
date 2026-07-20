from ktem.docqa.claim_aggregation import aggregate_answer_claims


def test_claim_aggregation_merges_duplicate_fact_and_unions_citations():
    answer, trace = aggregate_answer_claims(
        "Revenue increased to $10 million in 2022. [1]\n"
        "In 2022, revenue rose to $10 million. [2]"
    )

    assert answer.count("$10 million") == 1
    assert "[1]" in answer
    assert "[2]" in answer
    assert trace["duplicate_claim_count"] == 1


def test_claim_aggregation_keeps_conflicting_values_for_verifier():
    answer, trace = aggregate_answer_claims(
        "Revenue was $10 million in 2022. [1]\n" "Revenue was $12 million in 2022. [2]"
    )

    assert "$10 million" in answer
    assert "$12 million" in answer
    assert trace["conflict_count"] == 1
    assert trace["duplicate_claim_count"] == 0


def test_claim_aggregation_bypasses_json_tables_and_formula_outputs():
    json_answer = '{"hallucination list": []}'
    table_answer = "| Year | Revenue |\n|---|---|\n| 2022 | 10 |"
    formula_answer = "$$x = (a-b) / b$$"

    assert aggregate_answer_claims(json_answer)[0] == json_answer
    assert aggregate_answer_claims(table_answer)[0] == table_answer
    assert aggregate_answer_claims(formula_answer)[0] == formula_answer
