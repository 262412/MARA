from benchmark.route_output_agreement import route_output_agreement_rate


def test_route_output_agreement_reports_duplicate_route_weighting():
    predictions = [
        {
            "dataset_name": "qasper",
            "example_id": "same",
            "route": "text_rag",
            "answer_for_scoring": "yes",
        },
        {
            "dataset_name": "qasper",
            "example_id": "same",
            "route": "controller",
            "answer_for_scoring": "yes",
        },
        {
            "dataset_name": "qasper",
            "example_id": "different",
            "route": "text_rag",
            "answer_for_scoring": "yes",
        },
        {
            "dataset_name": "qasper",
            "example_id": "different",
            "route": "controller",
            "answer_for_scoring": "no",
        },
    ]

    assert route_output_agreement_rate(predictions) == 0.5
