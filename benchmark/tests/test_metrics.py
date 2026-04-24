from benchmark.metrics import (
    anls_score,
    element_hit_score,
    exact_match_score,
    false_abstention_score,
    formula_normalized_match_score,
    is_abstention_answer,
    latex_renderable_score,
    markdown_table_renderable_score,
    numeric_tolerance_score,
    span_recall_score,
    token_f1_score,
)


def test_exact_match_ignores_case_and_punctuation():
    assert exact_match_score("Revenue.", ["revenue"]) == 1.0


def test_token_f1_prefers_best_gold_answer():
    score = token_f1_score("net income was 10", ["income was 10", "other"])
    assert round(score, 4) == 0.8571


def test_anls_rewards_small_edit_distance():
    score = anls_score("internvl2", ["internvl"])
    assert score > 0.5


def test_element_hit_matches_gold_evidence_element_ids():
    score = element_hit_score(
        predicted_element_ids=["table-2", "cell-b2"],
        gold_evidence=[
            {"element_id": "table-1"},
            {"element_id": "cell-b2"},
        ],
    )
    assert score == 1.0


def test_span_recall_matches_predicted_text_against_gold_evidence_spans():
    score = span_recall_score(
        predicted_text="The report says revenue was 20 and profit was 5.",
        gold_evidence=[
            {"span": "revenue was 20"},
            {"span": "profit was 5"},
        ],
    )
    assert score == 1.0


def test_formula_normalized_match_ignores_whitespace_case_and_wrappers():
    assert formula_normalized_match_score("= SUM ( A1 : A3 )", ["sum(a1:a3)"]) == 1.0


def test_numeric_tolerance_accepts_close_values():
    assert numeric_tolerance_score("$1,001.00", ["1000"], tolerance=0.01) == 1.0
    assert numeric_tolerance_score("950", ["1000"], tolerance=0.01) == 0.0


def test_false_abstention_flags_supported_answers_rewritten_to_no_evidence():
    assert is_abstention_answer("文档证据无法支持该回答") is True
    assert false_abstention_score("文档证据无法支持该回答", ["Transformer"]) == 1.0
    assert false_abstention_score("The answer is Transformer.", ["Transformer"]) == 0.0


def test_markdown_table_renderable_score_requires_separator_row():
    renderable = """| Component | Input |
| :--- | :--- |
| Encoder | Embeddings |"""
    malformed = """| Component | Input |
| Encoder | Embeddings |"""

    assert markdown_table_renderable_score(renderable) == 1.0
    assert markdown_table_renderable_score(malformed) == 0.0


def test_latex_renderable_score_requires_formula_delimiters():
    assert latex_renderable_score(r"The update is $w_{t+1}=w_t-\eta\nabla L$.") == 1.0
    assert latex_renderable_score(r"The update is w_{t+1}=w_t-\eta\nabla L.") == 0.0
