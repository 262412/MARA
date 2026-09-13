from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "ktem"
CHAT_PAGE_FILE = PACKAGE_ROOT / "pages" / "chat" / "__init__.py"
CHAT_MESSAGE_EVENTS_FILE = PACKAGE_ROOT / "pages" / "chat" / "chat_message_events.py"


def test_chat_submit_event_chain_keeps_runtime_cache_and_persist_order():
    chat_page = CHAT_PAGE_FILE.read_text(encoding="utf-8")
    message_events = CHAT_MESSAGE_EVENTS_FILE.read_text(encoding="utf-8")

    assert "bind_chat_submit_events(" in chat_page
    assert "ports = chat_submit_ports(page)" in message_events
    submit_chain = message_events[
        message_events.index("def _submit_message_event") : message_events.index(
            "def _append_runtime_stream"
        )
    ]
    ordered_tokens = [
        "fn=page.submit_msg",
        "_append_runtime_stream(page, ports, chat_event)",
        "_append_request_cache(page, ports, chat_event)",
        "_append_post_stream_ui(",
        "_append_conversation_name_update(tail, ports, chat_event)",
    ]
    positions = [submit_chain.index(token) for token in ordered_tokens]
    assert positions == sorted(positions)

    helper_tokens = [
        "fn=with_completion_context(page.chat_fn)",
        "fn=cache_request_view(page.page_preview.cache_page_outputs)",
        "outputs=ports.clear_selection.gradio_outputs",
        "js=pdfview_js",
        "js=scroll_answer_panel_js",
        "suggest_name=page.check_and_suggest_name_conv",
        "page.chat_control.rename_conv",
    ]
    for token in helper_tokens:
        assert token in message_events
    assert "persist_data_source=page.persist_data_source" in message_events
