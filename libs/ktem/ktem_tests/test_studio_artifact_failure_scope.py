from typing import Any

from ktem.pages.chat.studio_artifact_controls import (
    generate_studio_artifact_panel_update,
)


class _FailingRuntime:
    def __init__(self):
        self.request = None

    def run_turn(self, request):
        self.request = request
        raise RuntimeError("artifact adapter down")


class _FailurePage:
    def __init__(self):
        self.docqa: Any = _FailingRuntime()
        self.knowledge_graph: Any = None

    @staticmethod
    def _resolve_persist_user_id(user_id, _request):
        return user_id

    def _build_selected_input_map(self, *selecteds):
        return {7: list(selecteds)}

    def _render_citations_card_html(self, retrieval_html=""):
        return f"citations:{retrieval_html}"


def test_failed_studio_artifact_uses_selected_sources_without_active_file(monkeypatch):
    page = _FailurePage()
    saved = []

    def save_failed_artifact(**kwargs):
        saved.append(kwargs)
        return {
            "type": kwargs["artifact_type"],
            "status": "failed",
            "source_scope": {"mode": "document", "source_ids": kwargs["source_ids"]},
            "generation": {"error": kwargs["error"]},
        }

    monkeypatch.setattr(
        "ktem.pages.chat.studio_artifact_status.save_failed_studio_artifact",
        save_failed_artifact,
    )

    result = generate_studio_artifact_panel_update(
        page,
        "quiz",
        "Focus on exam prep.",
        "document",
        "markdown",
        "medium",
        5,
        "conv-1",
        [],
        {},
        "mara",
        "gpt-test",
        "default",
        "default",
        "English",
        {},
        None,
        "user-1",
        "",
        "",
        1,
        "",
        "{}",
        "llm",
        "auto",
        "light",
        "",
        "",
        "selected-source",
    )

    assert saved[0]["source_ids"] == ["selected-source"]
    assert "Based on 1 source" in result[7]
    assert result[10]["visible"] is False
