"""Serve the production App with owned storage and deterministic model boundaries."""

import argparse
import json
import os
import sys
import threading
import time
from importlib import import_module
from pathlib import Path

from file_browser_barriers import FileBrowserBarriers
from indexing_lifetime_observer import IndexingLifetimeObserver
from web_operation_observer import bind_operation_observer
from web_seam_observer import studio_exports

from pytest_runtime_isolation import start_process_test_runtime


def serve(output):
    runtime = start_process_test_runtime()
    os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
    os.environ["ANONYMIZED_TELEMETRY"] = "False"
    os.environ["NO_PROXY"] = "localhost,127.0.0.1,::1"
    import pytest
    from ktem_tests.chat_submission_app_fixture import submission_app

    try:
        with pytest.MonkeyPatch.context() as patch:
            with submission_app(patch, runtime.paths.root) as (app, blocks):
                _indexing_boundaries(patch)
                observer = IndexingLifetimeObserver(patch, app.chat_page.file_index)
                try:
                    _launch(app, blocks, runtime.paths.root, output, observer)
                finally:
                    observer.close()
    finally:
        threading.setprofile(None)
        sys.setprofile(None)
        threading.settrace(None)  # type: ignore[arg-type]  # Python 3.10 stub
        sys.settrace(None)
        runtime.close()
        (output / "cleanup.json").write_text(
            json.dumps(
                {
                    "root": str(runtime.paths.root),
                    "removed": not runtime.paths.root.exists(),
                }
            ),
            encoding="utf-8",
        )


def _launch(app, blocks, root, output, observer):
    import gradio
    from ktem.assets import get_pdfjs_runtime_dir
    from ktem.auth.service import authenticate_password
    from ktem.preview.allowed_paths import build_gradio_allowed_paths
    from ktem_tests.chat_submission_app_fixture import seed_owned_document
    from theflow.settings import settings

    model_boundary = import_module("libs.ktem.ktem_tests.chat_submission_model_fixture")

    assert gradio.__version__ == "4.39.0"
    seed_owned_document(app, root)
    if os.environ.get("MARA_BROWSER_PUBLIC_FIXTURE") == "1":
        _seed_public_conversations()
    else:
        from ktem_tests.file_browser_app_fixture import seed_file_browser_documents

        seed_file_browser_documents(app, root)
    page = app.chat_page
    barriers = FileBrowserBarriers()
    trace, writes = _observe(page, barriers)
    operations = bind_operation_observer(blocks, page, barriers)
    dependencies = blocks.config["dependencies"]
    start = next(
        i
        for i, dep in enumerate(dependencies)
        if blocks.fns[dep["id"]].fn == page.submit_msg
    )
    roles = dict(
        zip(
            (
                "submit",
                "runtime",
                "cache",
                "clear",
                "pdf",
                "scroll",
                "suggest",
                "rename",
                "persist",
            ),
            (dep["id"] for dep in dependencies[start : start + 9]),
        )
    )
    roles.update(_selection_roles(dependencies, page.chat_control.conversation._id))
    blocks.queue().launch(
        server_name="127.0.0.1",
        server_port=8768,
        auth=authenticate_password,
        share=False,
        inbrowser=False,
        prevent_thread_lock=True,
        show_error=True,
        allowed_paths=build_gradio_allowed_paths(
            pdfjs_dir=get_pdfjs_runtime_dir(settings.KH_APP_DATA_DIR),
            gradio_temp_dir=os.environ["GRADIO_TEMP_DIR"],
            doc_dir=settings.KH_DOC_DIR,
        ),
    )

    barriers.bind_delivery(blocks._queue)
    _bind_evidence_routes(blocks, page, trace, writes, model_boundary, barriers)
    blocks.app.get("/owned-web-operations")(lambda: list(operations))
    _bind_indexing_lifetime_routes(blocks, observer)

    _write_ready(output, root, roles, blocks, page._indices_input[1]._id)
    deadline = time.monotonic() + 600
    try:
        while time.monotonic() < deadline and not (output / "stop").exists():
            time.sleep(0.2)
    finally:
        barriers.release_all()


def _bind_indexing_lifetime_routes(blocks, observer):
    @blocks.app.get("/owned-indexing-lifetime")
    def indexing_lifetime():
        return observer.snapshot()

    @blocks.app.post("/owned-indexing-lifetime/release")
    def release_embedding():
        observer.release()
        return {"released": True}

    @blocks.app.post("/owned-indexing-lifetime/release-deletion")
    def release_deletion_embedding():
        observer.release_deletion()
        return {"released": True}


def _bind_evidence_routes(blocks, page, trace, writes, model_boundary, barriers):
    @blocks.app.get("/owned-evidence")
    def evidence():
        return _read_evidence(blocks, page, trace, writes)

    @blocks.app.get("/owned-model-gate")
    def model_gate():
        return {
            "started": model_boundary.held_started.is_set(),
            "released": model_boundary.held_release.is_set(),
        }

    @blocks.app.post("/owned-model-gate/release")
    def release_model():
        model_boundary.held_release.set()
        return {"released": True}

    @blocks.app.post("/owned-file-browser-gate/arm")
    def arm_file_browser_gate(spec: dict):
        return barriers.arm(spec)

    @blocks.app.get("/owned-file-browser-gate")
    def file_browser_gate_status():
        return barriers.status()

    @blocks.app.post("/owned-file-browser-gate/release/{key}")
    def release_file_browser_gate(key: str):
        return barriers.release(key)


def _write_ready(output, root, roles, blocks, selector_id):
    import gradio

    dependencies = blocks.config["dependencies"]
    (output / "ready.json").write_text(
        json.dumps(
            {
                "roles": roles,
                "gradio": gradio.__version__,
                "root": str(root),
                "initial_selection_events": _initial_selection_events(
                    dependencies, selector_id
                ),
                "functions": {
                    dep["id"]: {
                        "name": blocks.fns[dep["id"]].name,
                        "targets": dep["targets"],
                        "trigger_after": dep["trigger_after"],
                        "inputs": dep["inputs"],
                        "outputs": dep["outputs"],
                    }
                    for dep in dependencies
                },
            }
        ),
        encoding="utf-8",
    )


def _initial_selection_events(dependencies, selector_id):
    """Find selector result producers in the real registered app-load chains."""
    by_id = {dep["id"]: dep for dep in dependencies}
    output_ids = {selector_id}
    for dep in dependencies:
        if not dep["backend_fn"] and selector_id in dep["outputs"]:
            output_ids.update(dep["inputs"])
    initial = []
    for dep in dependencies:
        if not output_ids.intersection(dep["outputs"]) or not dep["backend_fn"]:
            continue
        root = dep
        while root["trigger_after"] is not None:
            root = by_id[root["trigger_after"]]
        if any(event == "load" for _, event in root["targets"]):
            initial.append(dep["id"])
    assert initial
    return initial


def _selection_roles(dependencies, conversation_id):
    current = next(
        dep for dep in dependencies if (conversation_id, "select") in dep["targets"]
    )
    roles = {"conversation_select": current["id"]}
    while True:
        if current["backend_fn"]:
            roles["conversation_select_tail"] = current["id"]
        children = [
            dep for dep in dependencies if dep["trigger_after"] == current["id"]
        ]
        if not children:
            return roles
        assert len(children) == 1
        current = children[0]


def _observed_callbacks(page):
    from ktem.docqa._runtime_session_service import RuntimeSessionService
    from ktem.pages.chat.chat_completion import CompletionTail
    from ktem.pages.chat.studio_artifact_controls import (
        generate_studio_artifact_panel_update,
        regenerate_latest_studio_artifact_panel_update,
    )

    return [
        page.submit_msg,
        page.chat_fn,
        page.page_preview.cache_page_outputs,
        page.check_and_suggest_name_conv,
        page.chat_control.rename_conv,
        page.chat_control.new_conv,
        page.chat_control.delete_conv,
        page.chat_control.select_conv,
        page.chat_control.load_chat_history,
        page.persist_data_source,
        page.render_latest_reasoning_trace,
        page.first_indexing_file_fn,
        page.first_indexing_url_fn,
        page.refresh_chat_file_list,
        getattr(page, f"_index_{page.file_index.id}").load_files,
        getattr(page._app, f"_index_{page.file_index.id}").list_file,
        getattr(page._app, f"_index_{page.file_index.id}").delete_event,
        page.page_preview.on_selected_file_change,
        page.page_preview.refresh_selected_file_preview,
        page.page_preview.on_page_change,
        page.page_preview.on_page_set,
        page.page_preview.on_preview_tick,
        generate_studio_artifact_panel_update,
        regenerate_latest_studio_artifact_panel_update,
        CompletionTail.persist,
        RuntimeSessionService.persist_conversation_state,
    ]


def _observe(page, barriers):
    from ktem.db.models import Conversation, engine
    from sqlmodel import Session

    codes = {
        getattr(fn, "__func__", fn).__code__: fn.__qualname__
        for fn in _observed_callbacks(page)
    }
    trace, writes = [], []

    def observe(frame, event, arg):
        name = codes.get(frame.f_code)
        if name is None or event not in ("call", "return"):
            return
        values = frame.f_locals
        request = values.get("request")
        conversation_id = values.get("conversation_id", values.get("convo_id"))
        trace.append(
            {
                "callback": name,
                "event": event,
                "conversation_id": conversation_id,
                "username": getattr(request, "username", None),
                "session_hash": getattr(request, "session_hash", None),
                "file_id": values.get("file_id"),
                "file_name": values.get("file_name"),
                "file_path": values.get("file_path"),
                "preview_failed": (
                    name.startswith("ChatPagePreviewController.")
                    and name != "ChatPagePreviewController.cache_page_outputs"
                    and event == "return"
                    and arg is None
                ),
            }
        )
        barriers.observe(name, event, values, arg)
        if (
            name == "RuntimeSessionService.persist_conversation_state"
            and event == "return"
            and arg is not None
        ):
            with Session(engine) as session:
                row = session.get(Conversation, conversation_id)
                assert row is not None
                writes.append(
                    {
                        "conversation_id": conversation_id,
                        "origin_argument": values["origin"],
                        "data_source": json.loads(json.dumps(row.data_source)),
                    }
                )

    threading.setprofile(observe)
    sys.setprofile(observe)
    _observe_preview_exceptions(page.page_preview.on_preview_tick, trace)
    return trace, writes


def _observe_preview_exceptions(callback, trace):
    def observe(frame, event, arg):
        if frame.f_code is not callback.__func__.__code__:
            return None
        frame.f_trace_lines = False
        if event == "exception":
            values = frame.f_locals
            request = values.get("request")
            trace.append(
                {
                    "callback": callback.__qualname__,
                    "event": event,
                    "session_hash": getattr(request, "session_hash", None),
                    "file_id": values.get("file_id"),
                    "error_type": arg[0].__name__,
                    "error": str(arg[1]),
                    "preview_failed": False,
                }
            )
        return observe

    threading.settrace(observe)
    sys.settrace(observe)


def _read_evidence(blocks, page, trace, writes):
    from ktem.db.models import Conversation, User, engine
    from sqlmodel import Session, select
    from theflow.settings import settings

    with Session(engine) as session:
        rows = session.exec(
            select(Conversation).order_by(Conversation.date_created)
        ).all()
        states = []
        for key, state in blocks.state_holder.session_data.items():
            fields = (
                "_page_outputs_cache",
                "_request_chat_history",
                "_request_completion",
            )
            states.append(
                {
                    "session_hash": key,
                    **{
                        name: state.state_data.get(getattr(page, name)._id)
                        for name in fields
                    },
                }
            )
        return {
            "conversations": [row.model_dump(mode="json") for row in rows],
            "studio_exports": studio_exports(rows, settings.KH_APP_DATA_DIR),
            "callbacks": list(trace),
            "writes": list(writes),
            "queue_events": dict(blocks._queue.event_analytics),
            "states": states,
            "users": {
                user.username: user.id for user in session.exec(select(User)).all()
            },
            "groups": [
                {"id": row.id, "name": row.name, "user": row.user, "data": row.data}
                for row in session.exec(
                    select(page.file_index._resources["FileGroup"])
                ).all()
            ],
            "files": [
                {"id": row.id, "name": row.name, "user": row.user, "path": row.path}
                for row in session.exec(
                    select(page.file_index._resources["Source"])
                ).all()
            ],
        }


def _indexing_boundaries(patch):
    from ktem.auth.passwords import hash_password
    from ktem.db.models import User, engine
    from sqlmodel import Session

    from kotaemon.loaders.web_loader import WebReader

    with Session(engine) as session:
        for username in ("browser-other", "browser-controls"):
            session.add(
                User(
                    username=username,
                    username_lower=username,
                    password=hash_password("OwnedFixture7!"),
                    admin=False,
                )
            )
        session.commit()

    def fetch_owned_url(self, url):
        assert url == "https://example.org/owned-web-document", url
        return "The owned web document describes an observatory with seven telescopes."

    patch.setattr(WebReader, "fetch_url", fetch_owned_url)


def _seed_public_conversations():
    """Pre-existing public/private records for the isolated permissions scenario."""
    from ktem.db.models import Conversation, User, engine
    from sqlmodel import Session, select

    with Session(engine) as session:
        owner = session.exec(select(User).where(User.username == "browser-owner")).one()
        for public in (True, False):
            row = Conversation(
                user=owner.id,
                name="Owned public control" if public else "Owned private control",
                is_public=public,
            )
            row.data_source = {
                "messages": [["PUBLIC FIXTURE", "Owned persisted public answer."]],
                "retrieval_messages": ["Owned public reference"],
                "plot_history": [None],
                "origin": "web",
                "state": {},
                "selected": {"1": ["select", ["owned-observatory"], owner.id]},
            }
            session.add(row)
        session.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    serve(parser.parse_args().output.resolve())
