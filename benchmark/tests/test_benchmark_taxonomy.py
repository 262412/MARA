from benchmark.benchmark_taxonomy import (
    classify_failure_taxonomy,
    classify_routing_taxonomy,
    failure_taxonomy_by_route,
    failure_taxonomy_counts,
    routing_taxonomy_counts,
)


def _prediction(**overrides):
    prediction = {
        "dataset_name": "qasper",
        "route": "text_rag",
        "predicted_answer": "wrong answer",
        "gold_answers": ["gold answer"],
        "retrieved_hits": [{"text": "support"}],
        "metrics": {"f1": 0.0, "false_abstention": 0.0},
        "diagnostics": {
            "retrieved_count": 1,
            "failure_class": "none",
            "retrieval_failure_type": "none",
            "citation_failure_type": "none",
        },
        "verifier_observability": {
            "false_abstention": 0,
            "has_unsupported_claim": 0,
        },
    }
    prediction.update(overrides)
    return prediction


def test_classify_failure_taxonomy_prioritizes_operational_failures():
    assert (
        classify_failure_taxonomy(
            _prediction(error_type="route_timeout", error="timed out")
        )
        == "timeout"
    )
    assert (
        classify_failure_taxonomy(
            _prediction(
                error="connection refused",
                backend_status="unreachable",
            )
        )
        == "backend_unavailable"
    )
    assert (
        classify_failure_taxonomy(
            _prediction(error="unexpected failure", error_type="execution_error")
        )
        == "execution_error"
    )


def test_classify_failure_taxonomy_maps_quality_failures():
    assert (
        classify_failure_taxonomy(
            _prediction(retrieved_hits=[], diagnostics={"retrieved_count": 0})
        )
        == "empty_retrieval"
    )
    assert (
        classify_failure_taxonomy(
            _prediction(
                metrics={"false_abstention": 1.0}, predicted_answer="No evidence"
            )
        )
        == "false_abstention"
    )
    assert (
        classify_failure_taxonomy(
            _prediction(diagnostics={"citation_failure_type": "citation_miss"})
        )
        == "bad_citation"
    )
    assert (
        classify_failure_taxonomy(
            _prediction(
                verifier_observability={"has_unsupported_claim": 1},
                metrics={"f1": 1.0},
            )
        )
        == "unsupported_claim"
    )
    assert classify_failure_taxonomy(_prediction()) == "answer_mismatch"
    assert classify_failure_taxonomy(_prediction(metrics={"f1": 1.0})) == "none"


def test_classify_failure_taxonomy_uses_ragtruth_clean_negative_objective():
    prediction = _prediction(
        predicted_answer='{"hallucination list": []}',
        gold_answers=["The response being verified."],
        example_metadata={
            "dataset_family": "hallucination_verification",
            "labels": [],
        },
        metrics={"f1": 0.0},
    )

    assert classify_failure_taxonomy(prediction) == "none"


def test_classify_failure_taxonomy_uses_ragtruth_positive_span_objective():
    prediction = _prediction(
        predicted_answer='{"hallucination list": ["profit doubled"]}',
        gold_answers=["Revenue rose and profit doubled."],
        example_metadata={
            "dataset_family": "hallucination_verification",
            "labels": [{"label_type": "hallucination", "text": "profit doubled"}],
        },
        metrics={"f1": 0.0},
    )

    assert classify_failure_taxonomy(prediction) == "none"


def test_classify_failure_taxonomy_keeps_generic_qa_f1_mismatch():
    prediction = _prediction(
        predicted_answer='{"hallucination list": []}',
        gold_answers=["The response being verified."],
        metrics={"f1": 0.0},
    )

    assert classify_failure_taxonomy(prediction) == "answer_mismatch"


def test_classify_failure_taxonomy_does_not_infer_clean_negative_without_labels():
    for metadata in (
        {"dataset_family": "hallucination_verification"},
        {
            "dataset_family": "hallucination_verification",
            "labels": {"not": "a list"},
        },
    ):
        prediction = _prediction(
            predicted_answer='{"hallucination list": []}',
            gold_answers=["The response being verified."],
            example_metadata=metadata,
            metrics={"f1": 0.0},
        )

        assert classify_failure_taxonomy(prediction) == "answer_mismatch"


def test_classify_failure_taxonomy_rejects_malformed_json_without_labels():
    prediction = _prediction(
        predicted_answer="not json",
        example_metadata={"dataset_family": "hallucination_verification"},
        metrics={"f1": 1.0},
    )

    assert classify_failure_taxonomy(prediction) == "answer_mismatch"


def test_classify_failure_taxonomy_does_not_promote_ragtruth_detection_proxy():
    prediction = _prediction(
        predicted_answer='{"hallucination list": ["wrong span"]}',
        example_metadata={"dataset_family": "hallucination_verification"},
        metrics={"f1": 0.0, "ragtruth_positive_detected": 1.0},
    )

    assert classify_failure_taxonomy(prediction) == "answer_mismatch"


def test_classify_routing_taxonomy_normalizes_route_families():
    assert classify_routing_taxonomy({"route": "direct_answer"}) == "direct_baseline"
    assert classify_routing_taxonomy({"route": "text_rag"}) == "text_retrieval"
    assert classify_routing_taxonomy({"route": "page_image_rag_vlm"}) == (
        "visual_retrieval"
    )
    assert classify_routing_taxonomy({"route": "element_rag"}) == "element_retrieval"
    assert classify_routing_taxonomy({"route": "graph_rag_local"}) == "graph_retrieval"
    assert classify_routing_taxonomy({"route": "hybrid_rag"}) == "hybrid_retrieval"
    assert classify_routing_taxonomy({"route": "controller_auto"}) == "controller"
    assert classify_routing_taxonomy({"route": "crag_guarded"}) == "guarded_controller"
    assert classify_routing_taxonomy({"route": "vidore_retriever_only"}) == (
        "retriever_only"
    )


def test_taxonomy_summaries_count_predictions_and_skipped_routes():
    predictions = [
        _prediction(route="text_rag"),
        _prediction(
            route="crag_guarded",
            metrics={"false_abstention": 1.0},
            predicted_answer="No evidence",
        ),
    ]
    skipped_routes = [
        {
            "route_id": "page_image_rag_vlm",
            "backend_status": "not_configured",
            "skip_reason": "not_configured: MARA_VLM_BASE_URL",
        }
    ]

    assert failure_taxonomy_counts(
        "qasper",
        predictions,
        skipped_routes=skipped_routes,
    ) == [
        {
            "dataset_name": "qasper",
            "failure_taxonomy": "answer_mismatch",
            "count": 1,
            "unit": "prediction",
        },
        {
            "dataset_name": "qasper",
            "failure_taxonomy": "false_abstention",
            "count": 1,
            "unit": "prediction",
        },
        {
            "dataset_name": "qasper",
            "failure_taxonomy": "backend_unavailable",
            "count": 1,
            "unit": "route_skip",
        },
    ]
    assert failure_taxonomy_by_route(
        "qasper",
        predictions,
        skipped_routes=skipped_routes,
    )[-1] == {
        "dataset_name": "qasper",
        "route": "page_image_rag_vlm",
        "routing_taxonomy": "visual_retrieval",
        "failure_taxonomy": "backend_unavailable",
        "count": 1,
        "unit": "route_skip",
    }
    assert routing_taxonomy_counts("qasper", predictions) == [
        {
            "dataset_name": "qasper",
            "routing_taxonomy": "text_retrieval",
            "count": 1,
        },
        {
            "dataset_name": "qasper",
            "routing_taxonomy": "guarded_controller",
            "count": 1,
        },
    ]
