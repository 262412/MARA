import json

import pytest

from benchmark.baseline_registry import (
    assert_writable_benchmark_output,
    load_baseline_registry,
)


def test_baseline_20260705_records_immutable_contract_and_checksums():
    registry = load_baseline_registry("baseline_20260705")

    assert registry["immutable"] is True
    assert registry["complete_artifact_sets"] == 41
    assert registry["prediction_records"] == 3540
    assert registry["metrics"]["avg_f1"]["contract"] == "token_f1_v1"
    assert registry["metrics"]["avg_f1"]["value"] == 0.2284
    assert registry["checksums"]["statistical_per_example_metric_records.csv"]


def test_frozen_baseline_root_and_descendants_cannot_be_report_outputs(
    tmp_path,
):
    frozen = tmp_path / "baseline"
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "baseline_id": "test",
                "immutable": True,
                "artifact_root": str(frozen),
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="frozen benchmark baseline"):
        assert_writable_benchmark_output(frozen / "new-run", [registry_path])

    assert_writable_benchmark_output(tmp_path / "new-output", [registry_path])
