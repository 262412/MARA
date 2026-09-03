from __future__ import annotations

import pytest

from benchmark.qasper_quality_focus import (
    QASPER_QUALITY_FOCUS_CASES,
    QASPER_QUALITY_FOCUS_CONTRACT,
    QASPER_QUALITY_FOCUS_ROUTES,
    build_qasper_quality_focus_manifest,
)


def _source_manifest() -> dict:
    return {
        "schema_version": 2,
        "dataset_name": "qasper_dev_stat200",
        "documents": [
            {"document_id": f"doc-{index}", "path": f"/data/doc-{index}.txt"}
            for index in range(1, 7)
        ],
        "routes": [{"route_id": route} for route in QASPER_QUALITY_FOCUS_ROUTES],
        "examples": [
            {
                "example_id": case["example_id"],
                "document_ids": [f"doc-{index}"],
                "gold_answers": (
                    ["unanswerable"]
                    if case["gold_class"] == "unanswerable"
                    else ["an answer"]
                ),
            }
            for index, case in enumerate(QASPER_QUALITY_FOCUS_CASES, start=1)
        ],
    }


def test_quality_focus_manifest_is_new_six_by_three_diagnostic_matrix() -> None:
    manifest = build_qasper_quality_focus_manifest(_source_manifest())
    quality_focus = manifest["metadata"]["quality_focus"]

    assert manifest["dataset_name"] == "qasper_quality_focus_6x3"
    assert [example["example_id"] for example in manifest["examples"]] == [
        case["example_id"] for case in QASPER_QUALITY_FOCUS_CASES
    ]
    assert manifest["routes"] == [
        {"route_id": route} for route in QASPER_QUALITY_FOCUS_ROUTES
    ]
    assert quality_focus["contract_id"] == QASPER_QUALITY_FOCUS_CONTRACT
    assert quality_focus["legacy_sample_reused"] is False
    assert quality_focus["expected_prediction_count"] == 18
    assert [
        example["quality_focus"]["failure_class"] for example in manifest["examples"]
    ] == [case["failure_class"] for case in QASPER_QUALITY_FOCUS_CASES]


def test_quality_focus_manifest_fails_closed_on_route_drift() -> None:
    source = _source_manifest()
    source["routes"] = [{"route_id": "text_rag"}]

    with pytest.raises(ValueError, match="quality focus requires routes"):
        build_qasper_quality_focus_manifest(source)


def test_quality_focus_manifest_fails_closed_on_gold_class_drift() -> None:
    source = _source_manifest()
    source["examples"][-1]["gold_answers"] = ["a real answer"]

    with pytest.raises(ValueError, match="gold class mismatch"):
        build_qasper_quality_focus_manifest(source)
