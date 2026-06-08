from typing import Any

from ktem.pages.chat.studio_artifact_controls import (
    generate_studio_artifact_panel_update,
)


class _MindmapRuntime:
    def run_turn(self, request):
        raise AssertionError("Studio mindmap should use the graph service")


class _MindmapGraphService:
    def __init__(self):
        self.calls = []

    def get_graph_view(
        self,
        *,
        conversation_id,
        graph_source_ids,
        focus_file_id,
        force_rebuild,
    ):
        self.calls.append(
            {
                "conversation_id": conversation_id,
                "graph_source_ids": list(graph_source_ids),
                "focus_file_id": focus_file_id,
                "force_rebuild": force_rebuild,
            }
        )
        return {
            "html": "<div id='knowledge-graph-panel'>interactive graph</div>",
            "status": "ready",
            "status_message": "ready",
            "graph_source_ids": ["file-1", "file-2"],
            "graph": {"nodes": [{"id": "node-1", "label": "Topic"}], "edges": []},
            "support_pages": {"file-1": ["2"]},
            "support_chunk_ids": {"file-1": ["chunk-1"]},
        }


class _MindmapPage:
    def __init__(self):
        self.docqa = _MindmapRuntime()
        self.knowledge_graph = _MindmapGraphService()
        self.trace_artifact: dict[str, Any] | None = None

    def _build_selected_input_map(self, *selecteds):
        return {7: list(selecteds)}

    def _generate_answer_panel_html(
        self, preserved_history, user_input, ai_response, is_thinking=False
    ):
        assert preserved_history == [("previous", "answer")]
        assert user_input.startswith("Group concepts by system.")
        assert not is_thinking
        return f"answer:{ai_response}"

    def _render_reasoning_trace_html(
        self,
        question="",
        retrieval_html="",
        answer_html="",
        active_file_id="",
        page_number=None,
        artifact_payload=None,
    ):
        self.trace_artifact = artifact_payload
        return f"trace:{active_file_id}:{page_number}:{question[:10]}"

    def _render_citations_card_html(self, retrieval_html=""):
        return f"citations:{retrieval_html}"

    def _json_to_plot(self, graph_view):
        return f"plot:{graph_view['html']}"


def test_generate_studio_mindmap_uses_interactive_knowledge_graph(monkeypatch):
    page = _MindmapPage()
    saved = []

    def save_studio_mindmap_artifact(**kwargs):
        saved.append(kwargs)
        return {
            "type": "mindmap",
            "title": kwargs["title"],
            "payload": kwargs["payload"],
        }

    monkeypatch.setattr(
        "ktem.pages.chat.studio_artifact_controls.save_studio_mindmap_artifact",
        save_studio_mindmap_artifact,
    )

    result = _generate_mindmap(page)

    assert page.knowledge_graph.calls == [_expected_graph_call()]
    assert saved[0]["conversation_id"] == "conv-graph"
    assert saved[0]["prompt"].startswith("Group concepts by system.")
    assert saved[0]["source_scope"] == {
        "mode": "multi_document",
        "source_ids": ["file-1", "file-2"],
        "page": 2,
    }
    assert saved[0]["payload"]["interactive"] is True
    assert saved[0]["payload"]["graph"]["nodes"][0]["label"] == "Topic"
    assert page.trace_artifact == {
        "type": "mindmap",
        "title": "Interactive Mind Map",
        "payload": saved[0]["payload"],
    }
    assert result[0] == "conv-graph"
    assert result[1][-1][1] == "Interactive mind map generated."
    assert result[9] == ["file-1", "file-2"]
    assert result[10] == "plot:<div id='knowledge-graph-panel'>interactive graph</div>"
    assert (
        result[11]["html"] == "<div id='knowledge-graph-panel'>interactive graph</div>"
    )
    assert len(result) == 12


def _generate_mindmap(page):
    return generate_studio_artifact_panel_update(
        page,
        "mindmap",
        "Group concepts by system.",
        "multi-document",
        "html",
        "",
        0,
        "conv-graph",
        [("previous", "answer")],
        {},
        "mara",
        "gpt-test",
        "default",
        "default",
        "English",
        {"state": "old"},
        None,
        "user-1",
        "file-1",
        "paper.pdf",
        2,
        "Selected page evidence.",
        "{}",
        "llm",
        "auto",
        "light",
        "",
        "",
        "selector-group",
        ["file-2"],
    )


def _expected_graph_call():
    return {
        "conversation_id": "conv-graph",
        "graph_source_ids": ["file-1", "file-2"],
        "focus_file_id": "file-1",
        "force_rebuild": True,
    }
