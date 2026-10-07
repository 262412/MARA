"""Check installed Web callback assets outside the checkout and without overlays."""

import subprocess
from pathlib import Path

CHAT_CALLBACK_ASSETS = {
    "ktem/assets/js/file_browser_refresh.js",
    "ktem/assets/js/chat_input_focus.js",
    "ktem/assets/js/quick_urls_submit.js",
    "ktem/assets/js/recommended_papers.js",
    "ktem/assets/js/clear_bot_message_selection.js",
    "ktem/assets/js/pdfview.js",
    "ktem/assets/js/fetch_api_key.js",
    "ktem/assets/js/scroll_answer_panel.js",
    "ktem/assets/js/preview_drag_pan.js",
}


def run_chat_callback_smoke(python: Path, cwd: Path, env: dict[str, str]) -> None:
    validation = """
import os
import sys
from pathlib import Path

assert 'PYTHONPATH' not in os.environ
def offline(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo'):
        raise RuntimeError('Installed callback loading attempted network access')
sys.addaudithook(offline)

import ktem.pages.chat as chat
import ktem.index.file.ui as file_ui
from ktem.assets import ASSETS_DIR

prefix = Path(sys.prefix).resolve()
assert ASSETS_DIR.resolve().is_relative_to(prefix)
assert Path(chat.__file__).resolve().is_relative_to(prefix)
names = ('chat_input_focus', 'quick_urls_submit', 'recommended_papers',
         'clear_bot_message_selection', 'pdfview', 'fetch_api_key',
         'scroll_answer_panel', 'preview_drag_pan')
for name in names:
    resource = ASSETS_DIR / 'js' / (name + '.js')
    script = resource.read_text(encoding='utf-8')
    assert script.startswith('\\nfunction('), name
    assert getattr(chat, name + '_js') == script, name
assert file_ui.chat_input_focus_js == chat.chat_input_focus_js
assert file_ui.chat_input_focus_js_with_submit == chat.chat_input_focus_js
assert (ASSETS_DIR / 'js' / 'file_browser_refresh.js').is_file()
print('[wheel-smoke] installed ChatPage callback resources and aliases passed without PYTHONPATH')
"""
    clean_env = env.copy()
    clean_env.pop("PYTHONPATH", None)
    clean_env["GRADIO_ANALYTICS_ENABLED"] = "False"
    subprocess.run([python, "-B", "-c", validation], env=clean_env, cwd=cwd, check=True)
