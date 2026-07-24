from benchmark.element_locator_metrics import element_locator_hit_score
from benchmark.metrics import (
    anls_score,
    element_hit_score,
    exact_match_score,
    false_abstention_score,
    formula_normalized_match_score,
    hard_negative_rejection_score,
    image_quote_hit_score,
    is_abstention_answer,
    latex_renderable_score,
    markdown_table_renderable_score,
    modality_hit_score,
    multimodal_support_score,
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


def test_element_locator_hit_uses_source_page_and_alias_alignment():
    score = element_locator_hit_score(
        retrieved_hits=[
            {
                "source_id": "annual_report",
                "page_label": "12",
                "element_id": "text-12-3",
                "element_id_aliases": ["image4"],
                "element_type_aliases": ["figure", "image"],
                "source_backrefs": ["annual_report#page:12"],
            }
        ],
        gold_evidence=[
            {
                "document_id": "annual_report",
                "page": 12,
                "element_id": "image4",
                "element_type": "image",
            }
        ],
    )

    assert score == 1.0
    assert (
        element_hit_score(
            ["text-12-3"],
            [{"document_id": "annual_report", "page": 12, "element_id": "image4"}],
        )
        == 0.0
    )


def test_modality_hit_uses_expected_modality_and_evidence_metadata():
    assert (
        modality_hit_score(
            "table",
            expected_modality="table",
            evidence_metadata={"has_table_evidence": True},
            retrieved_hits=[],
            gold_evidence=[],
        )
        == 1.0
    )
    assert (
        modality_hit_score(
            "figure",
            expected_modality="figure",
            evidence_metadata={"has_figure_evidence": False},
            retrieved_hits=[{"element_type": "figure_caption"}],
            gold_evidence=[],
        )
        == 1.0
    )
    assert (
        modality_hit_score(
            "slide",
            expected_modality="text",
            evidence_metadata={"has_slide_evidence": True},
            retrieved_hits=[],
            gold_evidence=[],
        )
        is None
    )


def test_span_recall_matches_predicted_text_against_gold_evidence_spans():
    score = span_recall_score(
        predicted_text="The report says revenue was 20 and profit was 5.",
        gold_evidence=[
            {"span": "revenue was 20"},
            {"span": "profit was 5"},
        ],
    )
    assert score == 1.0


def test_image_quote_hit_matches_visual_gold_evidence_quotes():
    score = image_quote_hit_score(
        predicted_text="The visual page says revenue rose by product segment.",
        gold_evidence=[
            {"modality": "page_image", "image_quote": "revenue rose"},
            {"modality": "text", "image_quote": "ignored text quote"},
        ],
    )

    assert score == 1.0


def test_multimodal_support_scores_gold_modalities_in_evidence_bundle():
    score = multimodal_support_score(
        evidence_bundle={
            "items": [
                {"modality": "page_image"},
                {"modality": "table"},
            ]
        },
        retrieved_hits=[],
        gold_evidence=[
            {"modality": "page_image"},
            {"element_type": "table"},
        ],
    )

    assert score == 1.0


def test_hard_negative_rejection_scores_absent_negative_hits():
    rejected = hard_negative_rejection_score(
        retrieved_hits=[{"doc_id": "positive"}],
        evidence_bundle={"items": [{"evidence_id": "page-image:positive"}]},
        gold_evidence=[
            {
                "evidence_id": "positive",
                "hard_negative_ids": ["page-image:negative"],
            }
        ],
    )
    selected = hard_negative_rejection_score(
        retrieved_hits=[{"doc_id": "page-image:negative"}],
        evidence_bundle={"items": [{"evidence_id": "page-image:negative"}]},
        gold_evidence=[
            {
                "evidence_id": "positive",
                "hard_negative_ids": ["page-image:negative"],
            }
        ],
    )

    assert rejected == 1.0
    assert selected == 0.0


def test_formula_normalized_match_ignores_whitespace_case_and_wrappers():
    assert formula_normalized_match_score("= SUM ( A1 : A3 )", ["sum(a1:a3)"]) == 1.0


def test_numeric_tolerance_accepts_close_values():
    assert numeric_tolerance_score("$1,001.00", ["1000"], tolerance=0.01) == 1.0
    assert numeric_tolerance_score("950", ["1000"], tolerance=0.01) == 0.0


def test_numeric_tolerance_does_not_match_shared_year_in_descriptive_answers():
    prediction = "In FY2023, SG&A expense was 23.8% of revenue because of advertising."
    gold = [
        (
            "In FY2023, SG&A increased because advertising and selling costs "
            "rose by 12% and 28% from FY2022."
        )
    ]

    assert numeric_tolerance_score(prediction, gold) == 0.0


def test_numeric_tolerance_still_matches_answer_shaped_currency_values():
    assert numeric_tolerance_score("$16,525", ["$16,525.00"]) == 1.0


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
