from types import SimpleNamespace

from ktem.pages.chat.source_scope import (
    build_selected_input_map,
    build_selector_source_map,
    extract_selected_ids_from_data_source,
    merge_unique_file_ids,
    normalize_selected_file_ids,
    sync_graph_source_ids,
)


def test_source_scope_normalizes_and_merges_file_ids():
    assert normalize_selected_file_ids(None) == []
    assert normalize_selected_file_ids("file-1") == ["file-1"]
    assert normalize_selected_file_ids(["file-1", "", None, "file-2"]) == [
        "file-1",
        "file-2",
    ]

    assert merge_unique_file_ids(["file-1", "file-2"], "file-1", ["file-3"]) == [
        "file-1",
        "file-2",
        "file-3",
    ]


def test_source_scope_extracts_selected_ids_from_persisted_selector_shapes():
    data_source = {
        "selected": {
            "9": ["select", ["file-1", "file-2"], 1],
            "10": ["disabled", "file-3", None],
            "11": ["all", ["file-4", "select", {"skip": True}], 1],
            "12": ("ignored", "tuple"),
            "13": ["file-2", "upload", ["file-5", ("skip",)]],
        }
    }

    assert extract_selected_ids_from_data_source(data_source) == [
        "file-1",
        "file-2",
        "file-3",
        "file-4",
        "file-5",
    ]


def test_source_scope_builds_selector_maps_and_selected_input_map():
    indices = [
        SimpleNamespace(id=9, selector=0),
        SimpleNamespace(id=10, selector=(0, 2)),
        SimpleNamespace(id=11, selector=None),
        SimpleNamespace(id=12, selector=5),
    ]

    selected_inputs = build_selected_input_map(indices, ("file-1", "unused", "file-3"))

    assert selected_inputs == {9: "file-1", 10: ["file-1", "file-3"]}
    assert build_selector_source_map(
        [
            ["Report.pdf", "file-1"],
            ["Group", '["file-1", "file-2"]'],
            ["", "file-3"],
            ["Invalid"],
        ]
    ) == {"file-1": "Report.pdf", "file-3": "file-3"}


def test_source_scope_syncs_graph_ids_against_available_sources():
    assert sync_graph_source_ids(["file-1", "file-3"], {"file-1": "Report"}, {}) == [
        "file-1"
    ]
    assert sync_graph_source_ids(["file-1"], {}, {}) == []
    assert (
        sync_graph_source_ids(
            ["file-1", "file-2"],
            {},
            {"file-2": "Slides"},
        )
        == []
    )
