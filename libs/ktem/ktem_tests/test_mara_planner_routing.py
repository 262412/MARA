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
    assert decision["route_scores"]["doc_page_image"] > decision["route_scores"][
        "hybrid"
    ]
