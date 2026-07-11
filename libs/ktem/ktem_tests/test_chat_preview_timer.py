from pathlib import Path
from types import SimpleNamespace

from ktem.pages.chat.page_preview_callbacks import poll_office_conversion

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "ktem"
CHAT_PAGE_FILE = PACKAGE_ROOT / "pages" / "chat" / "__init__.py"
CHAT_PANEL_FILE = PACKAGE_ROOT / "pages" / "chat" / "chat_panel.py"
CHAT_PREVIEW_EVENTS_FILE = PACKAGE_ROOT / "pages" / "chat" / "chat_preview_events.py"


def _read_chat_page() -> str:
    return CHAT_PAGE_FILE.read_text(encoding="utf-8")


def _read_chat_panel() -> str:
    return CHAT_PANEL_FILE.read_text(encoding="utf-8")


def _read_chat_preview_events() -> str:
    return CHAT_PREVIEW_EVENTS_FILE.read_text(encoding="utf-8")


def test_preview_timer_does_not_repaint_thumbnail_strip_by_default():
    chat_page = _read_chat_page()
    chat_panel = _read_chat_panel()
    preview_events = _read_chat_preview_events()

    assert "gr.Timer(value=2.0, active=False)" in chat_panel
    assert "bind_chat_preview_events(" in chat_page
    timer_chain = preview_events.split(
        "page.chat_panel.preview_refresh_timer.tick(", 1
    )[1].split("bind_preview_page_button(", 1)[0]
    assert "fn=page.page_preview.on_preview_tick" in timer_chain
    assert "fn=refresh_page_context_view" not in timer_chain
    assert "self.page_thumbnail_strip" not in timer_chain


def test_office_poll_skips_incomplete_legacy_preview_state():
    controller = SimpleNamespace(
        _get_office_job_status=lambda _path: (_ for _ in ()).throw(
            AssertionError("empty legacy state must not poll conversion")
        )
    )

    poll_office_conversion(controller, None, "")
