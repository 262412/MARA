from benchmark.statistical_significance import (
    bootstrap_ci_by_dataset_route,
    controller_oracle_regret_rows,
    paired_route_delta_rows,
    route_win_loss_tie_rows,
)


def _records():
    return [
        {"dataset": "d1", "example_id": "a", "route": "text_rag", "f1": 0.2},
        {"dataset": "d1", "example_id": "a", "route": "controller_auto", "f1": 0.4},
        {"dataset": "d1", "example_id": "a", "route": "page_image_rag_vlm", "f1": 0.3},
        {"dataset": "d1", "example_id": "b", "route": "text_rag", "f1": 0.5},
        {"dataset": "d1", "example_id": "b", "route": "controller_auto", "f1": 0.1},
        {"dataset": "d1", "example_id": "b", "route": "page_image_rag_vlm", "f1": 0.6},
        {"dataset": "d1", "example_id": "c", "route": "text_rag", "f1": 0.3},
        {"dataset": "d1", "example_id": "c", "route": "controller_auto", "f1": 0.3},
    ]


def test_paired_route_delta_rows_align_by_example_id():
    rows = paired_route_delta_rows(
        _records(),
        baseline_route="text_rag",
        candidate_route="controller_auto",
        metric="f1",
    )

    assert rows == [
        {
            "dataset": "d1",
            "example_id": "a",
            "baseline_route": "text_rag",
            "candidate_route": "controller_auto",
            "baseline_f1": 0.2,
            "candidate_f1": 0.4,
            "delta_f1": 0.2,
        },
        {
            "dataset": "d1",
            "example_id": "b",
            "baseline_route": "text_rag",
            "candidate_route": "controller_auto",
            "baseline_f1": 0.5,
            "candidate_f1": 0.1,
            "delta_f1": -0.4,
        },
        {
            "dataset": "d1",
            "example_id": "c",
            "baseline_route": "text_rag",
            "candidate_route": "controller_auto",
            "baseline_f1": 0.3,
            "candidate_f1": 0.3,
            "delta_f1": 0.0,
        },
    ]


def test_route_win_loss_tie_rows_counts_paired_deltas():
    rows = route_win_loss_tie_rows(
        _records(),
        baseline_route="text_rag",
        candidate_route="controller_auto",
        metric="f1",
    )

    assert rows == [
        {
            "dataset": "d1",
            "baseline_route": "text_rag",
            "candidate_route": "controller_auto",
            "wins": 1,
            "losses": 1,
            "ties": 1,
            "n": 3,
        }
    ]


def test_bootstrap_ci_by_dataset_route_reports_confidence_interval():
    rows = bootstrap_ci_by_dataset_route(
        _records(),
        baseline_route="text_rag",
        candidate_route="controller_auto",
        metric="f1",
        iterations=100,
        seed=7,
    )

    assert rows[0]["dataset"] == "d1"
    assert rows[0]["n"] == 3
    assert rows[0]["mean_delta_f1"] == -0.0667
    assert rows[0]["ci_low_f1"] <= rows[0]["mean_delta_f1"] <= rows[0]["ci_high_f1"]


def test_controller_oracle_regret_rows_compare_to_best_fixed_route():
    rows = controller_oracle_regret_rows(
        _records(),
        controller_route="controller_auto",
        metric="f1",
    )

    assert rows[0] == {
        "dataset": "d1",
        "example_id": "a",
        "controller_route": "controller_auto",
        "controller_f1": 0.4,
        "oracle_route": "page_image_rag_vlm",
        "oracle_f1": 0.3,
        "regret_f1": 0.0,
    }
    assert rows[1]["oracle_route"] == "page_image_rag_vlm"
    assert rows[1]["regret_f1"] == 0.5
