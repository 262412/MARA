from ktem.reasoning.mara_controller import planner_decision


def test_mara_planner_decision_routes_structured_calculation_to_hybrid_evidence():
    decision = planner_decision(
        {"task_type": "qa", "modalities": ["text"], "scope": "document"},
        question=(
            "What is the defect rate based on passed and failed counts in the "
            "inspection table?"
        ),
    )

    assert decision["route"] == "hybrid"
    assert decision["evidence_types"] == ["text", "page_image", "element"]
    assert decision["calculation_scope"] == "structured_document_calculation"


def test_mara_planner_decision_routes_quick_ratio_as_structured_calculation():
    decision = planner_decision(
        {"task_type": "qa", "modalities": ["text"], "scope": "document"},
        question=(
            "Does 3M have a reasonably healthy liquidity profile based on its "
            "quick ratio for Q2 of FY2023?"
        ),
    )

    assert decision["route"] == "hybrid"
    assert decision["evidence_types"] == ["text", "page_image", "element"]
    assert decision["calculation_scope"] == "structured_document_calculation"
    assert "compatibility_scope" not in decision


def test_mara_planner_routes_direct_finance_amount_with_period_and_unit_as_numeric():
    decision = planner_decision(
        {
            "task_type": "qa",
            "modalities": ["text"],
            "available_modalities": ["page_image"],
            "scope": "document",
        },
        question=(
            "What is the FY2021 capital expenditure amount in USD billions "
            "for PepsiCo? Use the statement of cash flows."
        ),
    )

    assert decision["route"] == "hybrid"
    assert decision["routing_features"]["structured_calculation"] is True
    assert decision["calculation_scope"] == "structured_document_calculation"


def test_mara_planner_does_not_report_alias_normalization_as_constraint():
    decision = planner_decision(
        {"task_type": "qa", "modalities": ["text"], "scope": "multi_document"},
        question="What are the key risks described in the report?",
        allowed_routes=[
            "doc_text",
            "hybrid",
            "doc_page_image",
            "doc_element",
            "graph_global",
        ],
    )

    assert decision["route"] == "doc_text"
    assert "Constrained" not in decision["reason"]


def test_mara_planner_keeps_text_route_for_text_strong_page_image_documents():
    decision = planner_decision(
        {
            "task_type": "qa",
            "modalities": ["text"],
            "available_modalities": ["page_image"],
            "scope": "multi_document",
        },
        question="What are the key financial metrics and potential risks?",
        allowed_routes=[
            "doc_text",
            "hybrid",
            "doc_page_image",
            "doc_element",
            "graph_global",
        ],
    )

    assert decision["route"] == "doc_text"
    assert decision["evidence_types"] == ["text"]
    assert decision["routing_features"]["visual_intent"] is False
    assert decision["route_scores"]["doc_text"] > decision["route_scores"]["hybrid"]
    assert decision["latency_budget_reason"] == "text_route_avoids_visual_latency"


def test_mara_planner_uses_page_image_for_visual_slide_questions():
    decision = planner_decision(
        {
            "task_type": "qa",
            "modalities": ["slide"],
            "available_modalities": ["page_image"],
            "scope": "document",
        },
        question="What label is shown in the chart on this slide?",
        allowed_routes=[
            "doc_text",
            "hybrid",
            "doc_page_image",
            "doc_element",
            "graph_global",
        ],
    )

    assert decision["route"] == "doc_page_image"
    assert decision["evidence_types"] == ["page_image"]
    assert decision["routing_features"]["visual_intent"] is True
    assert (
        decision["route_scores"]["doc_page_image"] > decision["route_scores"]["hybrid"]
    )


def test_mara_planner_exposes_expected_quality_cost_and_skips_expensive_visual():
    decision = planner_decision(
        {
            "task_type": "qa",
            "modalities": ["text"],
            "available_modalities": ["page_image"],
            "scope": "multi_document",
        },
        question="What happened to revenue?",
        allowed_routes=[
            "doc_text",
            "hybrid",
            "doc_page_image",
            "doc_element",
            "graph_global",
        ],
        route_probe={
            "text": {
                "evidence_count": 3,
                "top_score": 0.92,
                "top_margin": 0.22,
                "locator_quality": 1.0,
                "has_text_or_ocr": True,
            },
            "visual": {
                "evidence_count": 2,
                "top_score": 0.7,
                "top_margin": 0.03,
                "locator_quality": 0.8,
                "has_text_or_ocr": True,
                "backend_healthy": True,
            },
        },
        dataset_family="mmdocrag",
    )

    assert decision["route"] == "doc_text"
    assert decision["route_confidence_by_modality"] == decision["route_confidences"]
    assert decision["expected_route_quality"]["doc_text"] > (
        decision["expected_route_quality"]["doc_page_image"]
    )
    assert decision["expected_route_cost"]["doc_page_image"] > (
        decision["expected_route_cost"]["doc_text"]
    )
    assert "doc_page_image" in decision["skipped_expensive_routes"]


def test_mara_planner_blocks_element_route_when_coverage_is_low():
    decision = planner_decision(
        {
            "task_type": "qa",
            "modalities": ["table"],
            "available_modalities": ["page_image"],
            "scope": "document",
        },
        question="What value is in the revenue table?",
        allowed_routes=[
            "doc_text",
            "hybrid",
            "doc_page_image",
            "doc_element",
            "graph_global",
        ],
        route_probe={
            "text": {
                "evidence_count": 2,
                "top_score": 0.72,
                "top_margin": 0.1,
                "locator_quality": 1.0,
                "has_text_or_ocr": True,
            },
            "element": {
                "evidence_count": 1,
                "top_score": 0.95,
                "top_margin": 0.4,
                "locator_quality": 0.0,
                "has_text_or_ocr": False,
            },
        },
    )

    assert decision["route"] != "doc_element"
    assert decision["expected_route_quality"]["doc_element"] == 0.0
    assert "doc_element" in decision["skipped_expensive_routes"]
