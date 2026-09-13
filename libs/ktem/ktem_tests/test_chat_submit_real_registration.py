"""Check Gradio's real dependency graph, including failure edges and demo tail."""

import os
import subprocess
import sys
from pathlib import Path
from typing import cast

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
        assert dependency["queue"] is True
        assert dependency["batch"] is False
        assert dependency["cancels"] == []
        assert dependency["trigger_mode"] == "once"
        fn = blocks.fns[dependency["id"]]
        assert fn.concurrency_limit == (20 if position in (0, 1, 8) else "default")
        if callback is not None:
            if position in (1, 2):
                assert fn.fn.__wrapped__ == callback
            elif position in (6, 7, 8):
                attribute = {
                    6: "suggest_name",
                    7: "rename_conversation",
                    8: "persist_data_source",
                }[position]
                assert getattr(fn.fn.__self__, attribute) == callback
            else:
                assert fn.fn == callback
        assert dependency["js"] == {4: pdfview_js, 5: scroll_answer_panel_js}.get(
            position
        )
    assert blocks.fns[chain[3]["id"]].fn() == ""
    assert blocks.fns[chain[4]["id"]].fn() is True
    # Gradio 4.39 needs a backend completion event to trigger the naming tail.
    assert blocks.fns[chain[5]["id"]].fn() is None
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
        _check_conversation_callbacks(blocks, page)
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


def _check_conversation_callbacks(blocks, page):
    import gradio as gr
    from gradio.helpers import special_args

    control = page.chat_control
    dependencies = blocks.config["dependencies"]
    request = gr.Request(username="browser-owner", session_hash="control-registration")
    for component, event, callback, inputs in (
        (control.btn_new, "click", control.new_conv, ["claimed"]),
        (control.btn_del_conf, "click", control.delete_conv, ["id", "claimed"]),
        (control.conversation, "select", control.select_conv, ["id", "claimed"]),
        (
            control.conversation_rn,
            "submit",
            control.rename_conv,
            ["id", "name", True, "claimed"],
        ),
    ):
        root = next(
            dep for dep in dependencies if dep["targets"] == [(component._id, event)]
        )
        fn = blocks.fns[root["id"]]
        assert getattr(fn.fn, "__wrapped__", fn.fn) == callback
        component_inputs = cast(list, inputs)
        injected, _, _ = special_args(fn.fn, list(component_inputs), request=request)
        assert injected == [*component_inputs, request]
        assert root["trigger_after"] is None
        assert root["trigger_only_on_success"] is False
        assert root["queue"] is True and root["batch"] is False
        assert root["cancels"] == [] and root["trigger_mode"] == "once"
        assert fn.concurrency_limit == "default"
        if event == "select":
            assert root["inputs"] == [control.conversation._id, page._app.user_id._id]
            assert root["outputs"] == _ids(
                [
                    control.conversation_id,
                    control.conversation,
                    control.conversation_rn,
                    page.chat_panel.chatbot,
                    page.followup_questions,
                    page.info_panel,
                    page.state_plot_panel,
                    page.state_retrieval_history,
                    page.state_plot_history,
                    control.cb_is_public,
                    page.state_chat,
                    *page._indices_input,
                    page._page_outputs_cache,
                ]
            )
        elif event == "submit":
            assert root["outputs"] == _ids(
                [control.conversation, control.conversation, control.conversation_rn]
            )
        else:
            assert root["outputs"] == _ids(
                [control.conversation_id, control.conversation]
            )


def test_real_registration_preserves_failure_edges_and_demo_difference():
    repository = Path(__file__).resolve().parents[3]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        [
            str(repository),
            *(str(repository / "libs" / name) for name in ("ktem", "kotaemon")),
            environment.get("PYTHONPATH", ""),
        ]
    )
    runtime = ActiveTestRuntime.start(environment)
    try:
        completed = subprocess.run(
            [sys.executable, "-B", str(Path(__file__).resolve())],
            env=environment,
            cwd=runtime.paths.root,
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
