"""Real index selector triples carry a mode, file values and an identity slot."""

import pytest
from ktem.pages.chat.studio_artifact_generation import (
    selected_source_ids_for_studio_artifact,
)
from ktem.pages.chat.studio_artifact_mindmap import generate_studio_mindmap_outputs


@pytest.mark.parametrize(
    "selected,expected",
    [
        (["disabled", [], -1], []),
        (["select", ['["a", "b"]', "a"], "owner"], ["a", "b"]),
        (["select", ["a"], "owner"], ["a"]),
    ],
)
def test_studio_selector_mapping_excludes_identity_and_expands_groups(
    selected, expected
):
    assert selected_source_ids_for_studio_artifact("", {1: selected}) == expected


def test_mindmap_uses_index_mapping_instead_of_last_identity_component():
    class Page:
        class knowledge_graph:
            @staticmethod
            def get_graph_view(**kwargs):
                assert kwargs["graph_source_ids"] == ["owned-a", "owned-b"]
                raise RuntimeError("graph boundary reached with source IDs")

    values = {
        "conversation_id": "owned conversation",
        "user_id": "owner",
        "qa_scope": "multi-document",
        "active_file_id": "",
        "selecteds": ("select", ["owned-a", "owned-b"], "owner"),
        "selected_inputs": {1: ["select", ["owned-a", "owned-b"], "owner"]},
    }
    with pytest.raises(RuntimeError, match="graph boundary reached"):
        generate_studio_mindmap_outputs(
            Page(), values, save_artifact=lambda **kwargs: {}
        )
