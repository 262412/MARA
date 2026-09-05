from __future__ import annotations

import pytest

from benchmark.reports import write_reports
from benchmark.summary import _route_metric_table


def test_route_metric_rows_have_fixed_policy_schema() -> None:
    rows = _route_metric_table(
        "sample",
        [
            {"route": "text_rag", "metrics": {}},
            {
                "route": "crag_guarded",
                "agent_mode": "thorough",
                "route_policy": "auto",
                "metrics": {},
            },
        ],
    )

    assert rows[0]["agent_modes"] == []
    assert rows[0]["route_policies"] == []
    assert rows[1]["agent_modes"] == ["thorough"]
    assert rows[1]["route_policies"] == ["auto"]


def test_write_reports_handles_heterogeneous_route_metric_rows(tmp_path):
    route_rows = [
        {
            "dataset_name": "sample",
            "route": "direct_answer",
            "num_predictions": 1,
            "route_policies": ["direct"],
        },
        {
            "dataset_name": "sample",
            "route": "text_rag",
            "num_predictions": 1,
            "route_policies": ["retrieve"],
        },
        {
            "dataset_name": "sample",
            "route": "controller_auto",
            "num_predictions": 1,
            "route_policies": ["auto"],
            "agent_modes": ["thorough"],
        },
    ]
    report = {
        "summary": {
            "suite_name": "Heterogeneous Route Suite",
            "dataset_name": "sample",
            "num_examples": 3,
            "num_documents": 1,
            "route_metric_table": route_rows,
        },
        "predictions": [],
        "documents": [],
    }

    run_dir = write_reports(report, tmp_path, "Heterogeneous Route Suite")

    assert (run_dir / "summary.json").is_file()
    assert (run_dir / "report.md").is_file()
    route_metrics = (run_dir / "route_metrics.csv").read_text(encoding="utf-8")
    assert len(route_metrics.splitlines()) == 4
    assert "route_policies" in route_metrics.splitlines()[0]
    assert "agent_modes" in route_metrics.splitlines()[0]


def test_write_csv_removes_temporary_file_when_atomic_replace_fails(
    tmp_path, monkeypatch
):
    from benchmark import artifact_publication, reports

    path = tmp_path / "route_metrics.csv"
    path.write_text("existing\n", encoding="utf-8")

    def fail_replace(source, destination):
        raise RuntimeError(f"simulated replace failure: {source} -> {destination}")

    monkeypatch.setattr(artifact_publication.os, "replace", fail_replace)

    with pytest.raises(RuntimeError, match="simulated replace failure"):
        reports._write_csv(path, [{"dataset_name": "sample"}])

    assert path.read_text(encoding="utf-8") == "existing\n"
    assert list(tmp_path.glob(f".{path.name}.*.tmp")) == []
