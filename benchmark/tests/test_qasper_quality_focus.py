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
                    ["false"]
                    if case["failure_class"] == "explicit_negative_control"
                    else ["unanswerable"]
                    if case["gold_class"] == "unanswerable"
                    else ["an answer"]
                ),
                "gold_evidence": (
                    [{"span": case["negative_control_evidence"]}]
                    if case["failure_class"] == "explicit_negative_control"
                    else []
                ),
                "metadata": (
                    {
                        "qasper_answer_annotations": [
                            {
                                "yes_no": False,
                                "unanswerable": False,
                                "evidence": [case["negative_control_evidence"]],
                            }
                        ]
                    }
                    if case["failure_class"] == "explicit_negative_control"
                    else {}
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


def test_quality_focus_uses_explicit_negative_and_safe_unanswerable_controls() -> None:
    explicit_negative_case = next(
        case
        for case in QASPER_QUALITY_FOCUS_CASES
        if case["failure_class"] == "explicit_negative_control"
    )
    negative_case = next(
        case
        for case in QASPER_QUALITY_FOCUS_CASES
        if case["failure_class"] == "unanswerable_control"
    )

    assert (
        explicit_negative_case["example_id"]
        == "c0bee6539eb6956a7347daa9d2419b367bd02064"
    )
    assert explicit_negative_case["negative_control_basis"] == (
        "explicit_source_negation"
    )
    assert explicit_negative_case["negative_control_evidence"] == (
        "has not improved the scores"
    )
    assert negative_case["example_id"] == "c34e80fbbfda0f1786d3b00e06cef5ada78a3f3c"
    assert negative_case["negative_control_basis"] == (
        "empty_gold_evidence_and_no_source_conclusion"
    )


def test_quality_focus_rejects_explicit_negative_case_without_negated_evidence() -> None:
    source = _source_manifest()
    explicit_negative = next(
        example
        for example in source["examples"]
        if example["example_id"] == "c0bee6539eb6956a7347daa9d2419b367bd02064"
    )
    explicit_negative["gold_evidence"] = [{"span": "The study compares systems."}]

    with pytest.raises(ValueError, match="explicit negative control"):
        build_qasper_quality_focus_manifest(source)


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
