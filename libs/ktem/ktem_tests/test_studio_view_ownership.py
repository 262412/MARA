"""Studio side effects remain owned; late presentation cannot replace a new view."""

from types import SimpleNamespace

import gradio as gr
import pytest
from gradio.helpers import special_args
from ktem.pages.chat import generation_store as store
from ktem.pages.chat.studio_callback_identity import bind_page_callback


@pytest.mark.parametrize(
    "changed", ["conversation", "page", "generation", "other", "none"]
)
@pytest.mark.parametrize("multiple", [False, True])
def test_studio_result_requires_original_browser_view(monkeypatch, changed, multiple):
    for name in (
        "GENERATION_CACHE",
        "ACTIVE_REQUESTS",
        "CURRENT_VIEW",
        "VIEW_REVISIONS",
    ):
        monkeypatch.setattr(store, name, {})
    store.set_current_view("browser", "file_1")
    request = SimpleNamespace(username="owner", session_hash="browser")
    outputs = tuple(range(12)) if multiple else "owned notebook HTML"
    effects = []

    def callback(page, conversation, request: gr.Request):
        effects.append((page, conversation, request))
        if changed == "conversation":
            store.reset_view("browser")
        elif changed == "page":
            store.set_current_view("browser", "file_2")
        elif changed == "generation":
            store.init_cache_entry(
                request_key="newer",
                session_key="browser",
                page_key="file_1",
                file_id="file",
                page_number=1,
                last_question="newer question",
                preserved_history=[],
            )
        elif changed == "other":
            store.reset_view("other browser")
        return outputs

    page = object()
    bound = bind_page_callback(callback, page)
    args, _, _ = special_args(bound, inputs=["conversation"], request=request)
    result = bound(*args)
    assert effects == [(page, "conversation", request)]
    if changed in {"conversation", "page", "generation"}:
        assert result == ((gr.skip(),) * 12 if multiple else gr.skip())
    else:
        assert result is outputs
