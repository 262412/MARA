"""Serve the production App with owned storage and deterministic model boundaries."""

import argparse
import json
import os
import sys
import threading
import time
from importlib import import_module
from pathlib import Path

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
                _launch(app, blocks, runtime.paths.root, output)
    finally:
        threading.setprofile(None)
        sys.setprofile(None)
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


def _launch(app, blocks, root, output):
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
    page = app.chat_page
    trace, writes = _observe(page)
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

    _write_ready(output, root, roles, blocks, page._indices_input[1]._id)
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline and not (output / "stop").exists():
        time.sleep(0.2)


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
    """Find initial selector writers in the real registered app-load chains."""
    by_id = {dep["id"]: dep for dep in dependencies}
    initial = []
    for dep in dependencies:
        if selector_id not in dep["outputs"]:
            continue
        root = dep
        while root["trigger_after"] is not None:
            root = by_id[root["trigger_after"]]
        if any(event == "load" for _, event in root["targets"]):
            initial.append(dep["id"])
    assert initial
    return initial


def _observe(page):
    from ktem.db.models import Conversation, engine
    from ktem.docqa._runtime_session_service import RuntimeSessionService
    from ktem.pages.chat.chat_completion import CompletionTail
    from sqlmodel import Session

    callbacks = [
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
        page.first_indexing_file_fn,
        page.first_indexing_url_fn,
        page.refresh_chat_file_list,
        page.page_preview.on_selected_file_change,
        page.page_preview.refresh_selected_file_preview,
        page.page_preview.on_page_change,
        page.page_preview.on_page_set,
        page.page_preview.on_preview_tick,
        CompletionTail.persist,
        RuntimeSessionService.persist_conversation_state,
    ]
    codes = {getattr(fn, "__func__", fn).__code__: fn.__qualname__ for fn in callbacks}
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
    return trace, writes


def _read_evidence(blocks, page, trace, writes):
    from ktem.db.models import Conversation, User, engine
    from sqlmodel import Session, select

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
            "callbacks": list(trace),
            "writes": list(writes),
            "queue_events": dict(blocks._queue.event_analytics),
            "states": states,
            "users": {
                user.username: user.id for user in session.exec(select(User)).all()
            },
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
