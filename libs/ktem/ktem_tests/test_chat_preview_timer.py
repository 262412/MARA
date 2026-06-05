from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "ktem"
CHAT_PAGE_FILE = PACKAGE_ROOT / "pages" / "chat" / "__init__.py"
CHAT_PANEL_FILE = PACKAGE_ROOT / "pages" / "chat" / "chat_panel.py"


def _read_chat_page() -> str:
    return CHAT_PAGE_FILE.read_text(encoding="utf-8")


def _read_chat_panel() -> str:
    return CHAT_PANEL_FILE.read_text(encoding="utf-8")


def test_preview_timer_does_not_repaint_thumbnail_strip_by_default():
    chat_page = _read_chat_page()
    chat_panel = _read_chat_panel()

    assert "gr.Timer(value=2.0, active=False)" in chat_panel
    timer_chain = chat_page.split("self.chat_panel.preview_refresh_timer.tick(", 1)[
        1
    ].split("self.chat_panel.prev_page_btn.click", 1)[0]
    assert "fn=self.page_preview.on_preview_tick" in timer_chain
    assert "fn=self.refresh_page_context_view" not in timer_chain
    assert "self.page_thumbnail_strip" not in timer_chain
