from kotaemon.indices import QueryRouter, route_query


def test_route_query_detects_formula_signals_and_hints():
    query = (
        "\u89e3\u91ca\u516c\u5f0f E = mc^2 "
        "\u4e2d\u6bcf\u4e2a\u53d8\u91cf\u548c\u7b26\u53f7"
    )
    decision = route_query(query)

    assert decision.query == query
    assert decision.modality == "formula"
    assert decision.modality_weights["formula"] > decision.modality_weights["text"]
    assert decision.retrieval_hints["boost_element_types"] == ["formula"]


def test_route_query_detects_formula_abbreviations_and_math_symbols():
    for query in (
        "show the eq. from appendix",
        "derive \u2211x with \u222b and \u03b1",
    ):
        decision = route_query(query)

        assert decision.modality == "formula"
        assert decision.modality_weights["formula"] > decision.modality_weights["text"]


def test_route_query_detects_table_signals_and_hints():
    query = (
        "\u6309\u6392\u540d\u8868\u683c\u5217\u51fa"
        "\u5e73\u5747\u5206\u6700\u5927\u548c\u6700\u5c0f\u7684 row"
    )
    decision = route_query(query)

    assert decision.modality == "table"
    assert decision.modality_weights["table"] > decision.modality_weights["text"]
    assert decision.retrieval_hints["boost_element_types"] == ["table"]


def test_route_query_detects_figure_signals_and_hints():
    decision = QueryRouter().route("compare the flowchart diagram and chart")

    assert decision.modality == "figure"
    assert decision.modality_weights["figure"] > decision.modality_weights["text"]
    assert decision.retrieval_hints["boost_element_types"] == ["figure"]


def test_route_query_returns_mixed_when_multiple_modalities_match():
    query = (
        "\u56fe\u8868\u4e2d alpha \u03b1 = 0.05 " "\u7684\u516c\u5f0f\u548c\u8868\u683c"
    )
    decision = route_query(query)

    assert decision.modality == "mixed"
    assert decision.modality_weights["formula"] > decision.modality_weights["text"]
    assert decision.modality_weights["figure"] > decision.modality_weights["text"]
    assert decision.modality_weights["table"] > decision.modality_weights["text"]
    assert decision.retrieval_hints["boost_element_types"] == [
        "formula",
        "figure",
        "table",
    ]


def test_route_query_defaults_to_text_for_plain_queries():
    decision = route_query("summarize the introduction")

    assert decision.modality == "text"
    assert decision.modality_weights["text"] == 1.0
    assert decision.retrieval_hints["boost_element_types"] == ["text"]
