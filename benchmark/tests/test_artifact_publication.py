from __future__ import annotations

import json

from benchmark.artifact_publication import atomic_write_jsonl, verify_artifact_contract
from benchmark.jsonl import read_jsonl
from benchmark.reports import write_reports


def test_jsonl_artifact_keeps_unicode_line_separator_characters_inside_records(tmp_path):
    row = {
        "example_id": "unicode",
        "route": "text",
        "evidence": "before\u2028middle\u2029after\u0085",
    }
    run_dir = write_reports(
        {
            "summary": {
                "suite_name": "Unicode Suite",
                "dataset_name": "sample",
                "num_examples": 1,
                "num_documents": 1,
            },
            "predictions": [row],
            "documents": [],
        },
        tmp_path,
        "Unicode Suite",
    )

    assert read_jsonl(run_dir / "predictions.jsonl") == [row]
    manifest = json.loads((run_dir / "artifact_manifest.json").read_text())
    assert manifest["files"]["predictions.jsonl"]["line_count"] == 1
    assert verify_artifact_contract(run_dir)["complete"] is True


def test_atomic_jsonl_write_accepts_a_streaming_iterable(tmp_path):
    output = tmp_path / "stream.jsonl"
    atomic_write_jsonl(
        output,
        ({"example_id": str(index), "route": "text"} for index in range(3)),
    )

    assert read_jsonl(output) == [
        {"example_id": "0", "route": "text"},
        {"example_id": "1", "route": "text"},
        {"example_id": "2", "route": "text"},
    ]


def test_artifact_contract_rejects_post_marker_mutation(tmp_path):
    run_dir = write_reports(
        {
            "summary": {
                "suite_name": "Mutation Suite",
                "dataset_name": "sample",
                "num_examples": 1,
                "num_documents": 1,
            },
            "predictions": [{"example_id": "one", "route": "text", "error": None}],
            "documents": [],
        },
        tmp_path,
        "Mutation Suite",
    )
    predictions = run_dir / "predictions.jsonl"
    predictions.write_text(predictions.read_text(encoding="utf-8") + " ", encoding="utf-8")

    try:
        verify_artifact_contract(run_dir)
    except ValueError as exc:
        assert "digest" in str(exc)
    else:
        raise AssertionError("mutated artifact was accepted")
