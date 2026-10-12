import asyncio

import gradio as gr
import pytest

from kotaemon.contribs.promptui.ui.blocks import ChatBlock
from kotaemon.contribs.promptui.ui.chat import construct_chat_ui


def test_promptui_constructs_with_current_gradio():
    demo = construct_chat_ui(
        {}, lambda: None, lambda *args: "answer", lambda *args: None, lambda: None
    )

    assert demo.enable_queue
    chatbots = [
        block for block in demo.blocks.values() if isinstance(block, gr.Chatbot)
    ]
    assert len(chatbots) == 1
    assert chatbots[0].sanitize_html is True
    assert chatbots[0].allow_tags is False


def test_chatblock_preserves_additional_outputs_and_blank_guard():
    calls = []

    def respond(message, history, session):
        calls.append((message, history, session))
        return "answer", "trace"

    with gr.Blocks(analytics_enabled=False):
        output = gr.Textbox()
        chat = ChatBlock(
            respond, additional_inputs=gr.State("session"), additional_outputs=output
        )

    response, history, trace = asyncio.run(chat._submit_fn("question", [], "session"))
    assert response == "answer"
    assert history == [
        {"role": "user", "content": "question"},
        {"role": "assistant", "content": "answer"},
    ]
    assert trace == "trace"
    assert calls == [("question", [], "session")]
    assert chat._append_message_to_history("", history) == history
    assert asyncio.run(chat._submit_fn("", history, "session")) == (
        None,
        history,
        gr.skip(),
    )
    assert calls == [("question", [], "session")]


def test_chatblock_keeps_unsupported_stream_explicit():
    with gr.Blocks(analytics_enabled=False):
        chat = ChatBlock(lambda message, history: "answer")

    with pytest.raises(NotImplementedError, match="Stream function"):
        asyncio.run(chat._stream_fn("question", []))


def test_promptui_tabs_expose_launch_theme(monkeypatch):
    from kotaemon.contribs.promptui import ui
    from kotaemon.contribs.promptui.themes import John

    monkeypatch.setattr(ui, "import_dotted_string", lambda *args, **kwargs: object())
    monkeypatch.setattr(
        ui, "build_pipeline_ui", lambda *args: gr.Blocks(analytics_enabled=False)
    )
    config = {
        "first.Pipeline": {"ui-type": "pipeline"},
        "second.Pipeline": {"ui-type": "pipeline"},
    }

    demo = ui.build_from_dict(config)

    assert isinstance(demo.gradio_launch_kwargs["theme"], John)
