"""Check Gradio's real dependency graph, including failure edges and demo tail."""

import os
import subprocess
import sys
from pathlib import Path

from pytest_runtime_isolation import ActiveTestRuntime


def _ids(components):
    if components is None:
        return []
    if not isinstance(components, (list, tuple)):
        components = [components]
    return [component._id for component in components]


def _check_chain(blocks, page, chain, *, demo):
    from ktem.pages.chat import pdfview_js, scroll_answer_panel_js
    from ktem.pages.chat.chat_gradio_adapters import chat_submit_ports

    ports = chat_submit_ports(page)
    roles = [
        "submit",
        "runtime",
        "cache",
        "clear_selection",
        "pdf_refresh",
        "scroll",
        "suggest_name",
        "rename",
    ]
    callbacks = [
        page.submit_msg,
        page.chat_fn,
        page.page_preview.cache_page_outputs,
        None,
        None,
        None,
        page.check_and_suggest_name_conv,
        page.chat_control.rename_conv,
    ]
    if not demo:
        roles.append("persist")
        callbacks.append(page.persist_data_source)
    assert len(chain) == len(roles)
    assert chain[0]["targets"] == [(page.chat_panel.text_input._id, "submit")]
    expected_success = [False, True, True, False, False, False, True, True, False]
    expected_progress = [
        "hidden",
        "minimal",
        "hidden",
        "hidden",
        "full",
        "full",
        "full",
        "hidden",
        "full",
    ]
    for position, (dependency, role, callback) in enumerate(
        zip(chain, roles, callbacks)
    ):
        port = getattr(ports, role)
        assert dependency["inputs"] == _ids(port.inputs)
        assert dependency["outputs"] == _ids(port.outputs)
        assert dependency["trigger_after"] == (
            None if position == 0 else chain[position - 1]["id"]
        )
        assert dependency["trigger_only_on_success"] is expected_success[position]
        assert dependency["show_progress"] == expected_progress[position]
        assert dependency["queue"] is (position != 5)
        assert dependency["batch"] is False
        assert dependency["cancels"] == []
        assert dependency["trigger_mode"] == "once"
        fn = blocks.fns[dependency["id"]]
        assert fn.concurrency_limit == (20 if position in (0, 1, 8) else "default")
        if callback is not None:
            assert fn.fn == callback
        assert dependency["js"] == {4: pdfview_js, 5: scroll_answer_panel_js}.get(
            position
        )
    assert blocks.fns[chain[3]["id"]].fn() == ""
    assert blocks.fns[chain[4]["id"]].fn() is True
    assert blocks.fns[chain[5]["id"]].fn is None
    assert chain[7]["outputs"][0] == chain[7]["outputs"][1]
    assert chain[1]["types"]["generator"] is True


def _check_real_registration(monkeypatch, root):
    from ktem.pages.chat import pdfview_js, scroll_answer_panel_js
    from ktem.pages.chat.chat_message_events import bind_chat_submit_events
    from ktem_tests.chat_submission_app_fixture import submission_app

    with submission_app(monkeypatch, root) as (app, blocks):
        page = app.chat_page
        dependencies = blocks.config["dependencies"]
        start = next(
            i
            for i, dep in enumerate(dependencies)
            if blocks.fns[dep["id"]].fn == page.submit_msg
        )
        _check_chain(blocks, page, dependencies[start : start + 9], demo=False)
        before = len(blocks.fns)
        with blocks:
            bind_chat_submit_events(
                page,
                demo_mode=True,
                pdfview_js=pdfview_js,
                scroll_answer_panel_js=scroll_answer_panel_js,
            )
        demo_chain = blocks.get_config_file()["dependencies"][before:]
        _check_chain(blocks, page, demo_chain, demo=True)


def test_real_registration_preserves_failure_edges_and_demo_difference():
    environment = os.environ.copy()
    runtime = ActiveTestRuntime.start(environment)
    try:
        completed = subprocess.run(
            [sys.executable, "-B", str(Path(__file__).resolve())],
            env=environment,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
    finally:
        runtime.close()
        assert not runtime.paths.root.exists()


if __name__ == "__main__":
    import pytest

    with pytest.MonkeyPatch.context() as patch:
        _check_real_registration(patch, Path(os.environ["MARA_PYTEST_RUNTIME_ROOT"]))
