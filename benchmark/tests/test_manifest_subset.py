from __future__ import annotations

import pytest

from benchmark.manifest_subset import build_manifest_subset


def _manifest() -> dict:
    return {
        "schema_version": 2,
        "dataset_name": "sample",
        "documents": [
            {"document_id": "doc-1", "path": "/data/doc-1.pdf"},
            {"document_id": "doc-2", "path": "/data/doc-2.pdf"},
            {"document_id": "doc-3", "path": "/data/doc-3.pdf"},
        ],
        "routes": [{"route_id": "text"}, {"route_id": "controller"}],
        "examples": [
            {"example_id": "first", "document_ids": ["doc-1"]},
            {"example_id": "second", "document_ids": ["doc-2", "doc-3"]},
        ],
    }


def test_manifest_subset_keeps_requested_order_routes_and_referenced_documents() -> (
    None
):
    source = _manifest()

    subset = build_manifest_subset(source, ["second", "first"])

    assert [example["example_id"] for example in subset["examples"]] == [
        "second",
        "first",
    ]
    assert [document["document_id"] for document in subset["documents"]] == [
        "doc-1",
        "doc-2",
        "doc-3",
    ]
    assert subset["routes"] == source["routes"]
    assert source == _manifest()


def test_manifest_subset_fails_closed_on_a_missing_example() -> None:
    with pytest.raises(ValueError, match="manifest examples not found: missing"):
        build_manifest_subset(_manifest(), ["missing"])


def test_manifest_subset_fails_closed_on_a_missing_document() -> None:
    source = _manifest()
    source["documents"] = source["documents"][:1]

    with pytest.raises(ValueError, match="doc-2, doc-3"):
        build_manifest_subset(source, ["second"])
