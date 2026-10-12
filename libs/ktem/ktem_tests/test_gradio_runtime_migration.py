from types import SimpleNamespace

import gradio as gr
import pytest


def test_chat_panel_constructs_with_current_gradio():
    from ktem.pages.chat.chat_panel import ChatPanel

    with gr.Blocks(analytics_enabled=False):
        panel = ChatPanel(SimpleNamespace(app_name="MARA"))

    assert panel.chatbot.visible is False
    assert panel.chatbot.sanitize_html is True
    assert panel.chatbot.allow_tags is False
    assert panel.chatbot.elem_id == "main-chat-bot"


def test_default_file_selection_keeps_disabled_scope():
    from ktem.index.file._selector_ui import FileSelector

    selector = FileSelector.__new__(FileSelector)
    selector._app = SimpleNamespace(f_user_management=True)
    with gr.Blocks(analytics_enabled=False):
        selector.on_building_ui()

    assert selector.mode.preprocess(selector.mode.value) == "disabled"
    assert selector.get_selected_ids(["disabled", ["unselected-file"], "owner"]) == []
    with pytest.raises(gr.Error, match="not in the list of choices"):
        selector.mode.preprocess("unexpected-mode")


@pytest.mark.parametrize(
    "history",
    [
        [],
        [["question", "answer"]],
        [["question", None]],
        [["", ""]],
        [[None, "notice"], ["next", "reply"]],
    ],
)
def test_chat_transport_preserves_saved_turn_pairs(history):
    from ktem.pages.chat.chat_panel import ChatPanel

    with gr.Blocks(analytics_enabled=False):
        panel = ChatPanel(SimpleNamespace(app_name="MARA"))

    wire = panel.chatbot.postprocess(history)
    assert panel.chatbot.preprocess(wire) == history
    assert len(wire.root) == 2 * len(history)


def test_app_styles_survive_gradio_mount(monkeypatch):
    from fastapi import FastAPI
    from ktem.app import BaseApp

    app = BaseApp.__new__(BaseApp)
    app.app_name = "MARA"
    app._theme = gr.themes.Base()
    app._css = ".mara { color: red; }"
    app._js = "() => window.mara = true"
    app._pdf_view_js = "() => {}"
    app._registered_child_pages = []
    app._events = {}
    monkeypatch.setattr(app, "ui", lambda: gr.Markdown("MARA"))
    app.settings_state = gr.State({})
    app.user_id = gr.State("default")
    blocks = app.make()

    gr.mount_gradio_app(FastAPI(), blocks, "/mara", **app.gradio_launch_kwargs)

    assert blocks.theme is app._theme
    assert blocks.css == app._css
    assert blocks.js == app._js
    assert "markmap" in blocks.head


@pytest.mark.parametrize(
    "index, expected", [(0, [0, 0]), (3, [1, 1]), ([2, 1], [2, 1])]
)
def test_message_selection_preserves_saved_turn_coordinates(index, expected):
    from ktem.pages.chat.chat_history import message_position

    assert message_position(index) == expected


@pytest.mark.parametrize("history", [["not a turn"], [["one"]], [["a", {}]]])
def test_chat_transport_rejects_invalid_saved_turns(history):
    from ktem.pages.chat.chat_history import ConversationChatbot

    with pytest.raises(ValueError, match="Conversation"):
        ConversationChatbot().postprocess(history)


def test_current_chat_selection_uses_the_saved_turn(monkeypatch):
    from ktem.pages.chat import ChatPage

    page = ChatPage.__new__(ChatPage)
    monkeypatch.setattr(
        page, "_render_citations_card_html", lambda value: "citation:" + value
    )
    monkeypatch.setattr(
        page, "_render_reasoning_trace_html", lambda **values: values["question"]
    )
    selected = gr.SelectData(None, {"index": 3, "value": "answer"})

    assert page.message_selected(["first", "second"], [None, "plot"], selected) == (
        "second",
        "plot",
        "citation:second",
        "Conversation turn 2",
    )


@pytest.mark.parametrize(
    "messages",
    [
        [{"role": "user", "content": "unpaired"}],
        [
            {"role": "assistant", "content": "reversed"},
            {"role": "user", "content": "order"},
        ],
    ],
)
def test_chat_transport_rejects_invalid_wire_turns(messages):
    from ktem.pages.chat.chat_history import ConversationChatbot

    payload = gr.Chatbot().postprocess(messages)
    with pytest.raises(ValueError, match="Conversation history"):
        ConversationChatbot().preprocess(payload)


def test_current_feedback_preserves_owner_and_saved_record(monkeypatch):
    from ktem.pages.chat import ChatPage

    calls = []
    page = ChatPage.__new__(ChatPage)
    monkeypatch.setattr(
        page, "_resolve_persist_user_id", lambda user, request: "resolved-owner"
    )
    monkeypatch.setattr(
        page,
        "docqa",
        SimpleNamespace(
            append_session_like=lambda *args, **kwargs: calls.append((args, kwargs))
        ),
        raising=False,
    )
    liked = gr.LikeData(
        None,
        {
            "index": 3,
            "value": {
                "role": "assistant",
                "content": [{"type": "text", "text": "answer"}],
            },
            "liked": True,
        },
    )

    page.is_liked("conversation", liked, user_id="spoofed")

    assert calls == [
        (("conversation", [1, 1], "answer", True), {"user_id": "resolved-owner"})
    ]


@pytest.mark.parametrize(
    "query",
    ["", "?embed=1&ktempage=2&file=%2Fmara%2Ffile%3D%2Ftmp%2Fpaper%2520name.pdf"],
)
def test_legacy_file_links_use_the_authenticated_gradio_route(tmp_path, query):
    from urllib.parse import urlsplit

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from ktem.index.file.download_http import download_app_kwargs

    allowed = tmp_path / "owned.txt"
    denied = tmp_path / "private.txt"
    allowed.write_text("owned preview", encoding="utf-8")
    denied.write_text("must stay private", encoding="utf-8")
    with gr.Blocks(analytics_enabled=False) as blocks:
        gr.Markdown("Preview")
    app = gr.mount_gradio_app(
        FastAPI(),
        blocks,
        "/mara",
        auth=[("owner", "test-only")],
        allowed_paths=[str(allowed)],
        app_kwargs=download_app_kwargs(
            SimpleNamespace(index_manager=SimpleNamespace(indices=[]))
        ),
    )
    with TestClient(app) as client:
        path = "/mara/file=" + allowed.as_posix() + query
        redirect = client.get(path, follow_redirects=False)
        assert redirect.status_code == 307
        assert redirect.headers["location"].startswith("/mara/gradio_api/file=")
        assert urlsplit(redirect.headers["location"]).query == query.lstrip("?")
        assert client.get(path).status_code == 401
        assert (
            client.post(
                "/mara/login", data={"username": "owner", "password": "test-only"}
            ).status_code
            == 200
        )
        assert client.get(path).text == "owned preview"
        blocked = client.get("/mara/file=" + denied.as_posix())
        assert blocked.status_code == 403
        assert "must stay private" not in blocked.text


def test_preview_browser_harness_keeps_styles_and_file_scope(tmp_path):
    import runpy
    from pathlib import Path

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    source = Path(__file__).resolve().parents[3] / "tests/browser/serve_preview_flow.py"
    create_app = runpy.run_path(str(source))["create_app"]
    pdfjs = tmp_path / "pdfjs"
    pdfjs.mkdir()
    viewer = pdfjs / "viewer.html"
    viewer.write_text("owned viewer", encoding="utf-8")
    private = tmp_path / "private.txt"
    private.write_text("must stay private", encoding="utf-8")
    demo = create_app(pdfjs)
    app = gr.mount_gradio_app(
        FastAPI(), demo, "/", **demo.gradio_launch_kwargs, allowed_paths=[str(pdfjs)]
    )
    with TestClient(app) as client:
        config = client.get("/config").json()
        assert "main-pdf-preview" in config["css"]
        assert pdfjs.as_posix() in config["js"]
        assert client.get("/file=" + viewer.as_posix()).text == "owned viewer"
        denied = client.get("/file=" + private.as_posix())
        assert denied.status_code == 403
        assert "must stay private" not in denied.text
