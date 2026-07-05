from ktem.reasoning.mara import MaraAgentPipeline


def test_selected_source_summary_routes_to_document_text(monkeypatch):
    captured = {}

    def capture_execute(
        self,
        message,
        conv_id,
        history,
        understanding,
        planner_payload,
        kwargs,
        **_extra,
    ):
        del self, message, conv_id, history, kwargs
        captured["understanding"] = dict(understanding)
        captured["planner_payload"] = dict(planner_payload)
        raise RuntimeError("stop after planner")

    monkeypatch.setattr(MaraAgentPipeline, "execute_controller_route", capture_execute)
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.allowed_routes = [
        "doc_text",
        "hybrid",
        "doc_page_image",
        "doc_element",
        "graph_global",
    ]
    pipeline.selected_file_ids = ["source-1"]
    pipeline.selected_text = "The selected article text is available to the runtime."

    try:
        list(pipeline.stream("Summarize the selected source.", "conv-1", []))
    except RuntimeError as exc:
        assert str(exc) == "stop after planner"

    assert captured["understanding"]["selected_source_context"] is True
    assert captured["planner_payload"]["decision"]["route"] == "doc_text"


def test_selected_source_context_exposes_locator_hints(monkeypatch):
    captured = {}

    def capture_execute(
        self,
        message,
        conv_id,
        history,
        understanding,
        planner_payload,
        kwargs,
        **_extra,
    ):
        del self, message, conv_id, history, planner_payload, kwargs
        captured["understanding"] = dict(understanding)
        raise RuntimeError("stop after planner")

    monkeypatch.setattr(MaraAgentPipeline, "execute_controller_route", capture_execute)
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.allowed_routes = ["doc_element"]
    pipeline.selected_file_ids = ["source-1"]
    pipeline.active_file_id = "source-1"
    pipeline.page_number = 7

    try:
        list(pipeline.stream("Which table lists revenue?", "conv-1", []))
    except RuntimeError as exc:
        assert str(exc) == "stop after planner"

    assert captured["understanding"]["source_ids"] == ["source-1"]
    assert captured["understanding"]["pages"] == [7]
