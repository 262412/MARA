"""Effective Gradio callback strings frozen before R3-D resource migration."""

import hashlib

# Captured from 4b8215c3 (unchanged ChatPage scripts from the round baseline).
EXPECTED = {
    "chat_input_focus_js": "da22684f54d3aa39e79f7c4eade5ad50684a679c4f793b1169eb57c97dfb76ac",
    "quick_urls_submit_js": "81c5eb898ed689c8a94ac4fdfc769e9704d5cc930f97dffc41e1aa6a1d6dd2ef",
    "recommended_papers_js": "f3965368f6bdb8a330108ab6be016e52a5ff87c78f7192970f6d09ba998e8135",
    "clear_bot_message_selection_js": "6d845ba92aee42548734cfb84f5c7294736caadb122f6056e623a455ea4bf3b8",
    "pdfview_js": "69307d3b5a39b2b8d532aadaa798967de42879135cd08c30e0b81c910e8e22e9",
    "fetch_api_key_js": "a64df388b53b97497f9d76679413aa825bd6ea5706265f9f9b2ffe2c8c641076",
    "scroll_answer_panel_js": "36466c2c8e373efc91affbc50f63df0dcfe287c48278d1df0b6fa02ec44bfd85",
    "preview_drag_pan_js": "37d94c1a5250aee8761aa0feeb86932ff929b75d80b8b360695f164b5d177aaf",
}


def test_effective_callback_strings_and_old_aliases():
    import ktem.index.file.ui as file_ui
    import ktem.pages.chat as chat

    for name, digest in EXPECTED.items():
        value = getattr(chat, name)
        assert value.startswith("\nfunction(")
        assert hashlib.sha256(value.encode("utf-8")).hexdigest() == digest, name
    assert file_ui.chat_input_focus_js == chat.chat_input_focus_js
    assert file_ui.chat_input_focus_js_with_submit == chat.chat_input_focus_js
