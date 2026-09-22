"""Failures in the owned browser fixture must not strand a later release."""

import asyncio
import importlib
import json
import subprocess
import sys
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import Any

import pytest


@pytest.fixture
def modules(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parent / "browser"))
    return (
        importlib.import_module("serve_chat_submission"),
        importlib.import_module("run_chat_submission"),
        importlib.import_module("file_browser_barriers"),
    )


def fail_release(*args, **kwargs):
    raise RuntimeError("owned delivery release failed")


def test_release_all_attempts_later_barrier_after_delivery_failure(modules):
    barriers = modules[2].FileBrowserBarriers()
    for key in ("first", "later"):
        barriers.arm({"key": key})
    barriers.gates["first"]["deliver"] = fail_release
    with pytest.raises(RuntimeError):
        barriers.release_all()
    assert barriers.gates["first"]["release"].is_set()
    assert barriers.gates["later"]["release"].is_set()


def launch_fixture(monkeypatch, sut, output):
    model = SimpleNamespace(
        held_started=Event(),
        held_finished=Event(),
        held_release=Event(),
        generator_finished=Event(),
        stream_snapshot=lambda: {},
        worker_snapshot=lambda: {},
    )
    stubs = {
        "gradio": SimpleNamespace(__version__="4.39.0"),
        "ktem.assets": SimpleNamespace(get_pdfjs_runtime_dir=lambda root: root),
        "ktem.auth.service": SimpleNamespace(authenticate_password=object()),
        "ktem.preview.allowed_paths": SimpleNamespace(
            build_gradio_allowed_paths=lambda **kw: []
        ),
        "ktem_tests.chat_submission_app_fixture": SimpleNamespace(
            seed_owned_document=lambda *args: None
        ),
        "theflow.settings": SimpleNamespace(
            settings=SimpleNamespace(KH_APP_DATA_DIR=output, KH_DOC_DIR=output)
        ),
        "ktem.index.file.download_http": SimpleNamespace(
            download_app_kwargs=lambda app: {}
        ),
    }
    for name, module in stubs.items():
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setenv("MARA_BROWSER_PUBLIC_FIXTURE", "1")
    monkeypatch.setattr(sut, "import_module", lambda name: model)
    for name in (
        "_seed_public_conversations",
        "_bind_evidence_routes",
        "_bind_indexing_lifetime_routes",
    ):
        monkeypatch.setattr(sut, name, lambda *args: None)
    monkeypatch.setattr(sut, "_observe", lambda *args: ([], []))
    monkeypatch.setattr(sut, "bind_operation_observer", lambda *args: [])
    monkeypatch.setattr(sut, "observe_queue_cancellations", lambda *args: None)
    monkeypatch.setattr(sut, "_selection_roles", lambda *args: {})
    monkeypatch.setattr(
        sut, "_write_ready", lambda *args: (output / "stop").write_text("stop")
    )
    barriers = SimpleNamespace(
        bind_delivery=lambda queue: None, release_all=fail_release, status=lambda: {}
    )
    monkeypatch.setattr(sut, "FileBrowserBarriers", lambda: barriers)
    component = SimpleNamespace(_id=1)
    page = SimpleNamespace(
        submit_msg=object(),
        chat_control=SimpleNamespace(conversation=component),
        _indices_input=[component, component],
        file_index=SimpleNamespace(id=1),
        _app=object(),
    )
    blocks = SimpleNamespace(
        config={"dependencies": [{"id": i} for i in range(9)]},
        fns={i: SimpleNamespace(fn=page.submit_msg) for i in range(9)},
        _queue=SimpleNamespace(
            event_analytics={}, active_jobs=[], event_queue_per_concurrency_id={}
        ),
        app=SimpleNamespace(get=lambda path: lambda fn: fn),
        launch=lambda **kw: None,
    )
    blocks.queue = lambda: blocks
    return SimpleNamespace(chat_page=page), blocks, model


def test_ui_release_failure_cannot_prevent_model_release(
    modules, monkeypatch, tmp_path
):
    serve = modules[0]
    app, blocks, model = launch_fixture(monkeypatch, serve, tmp_path)
    with pytest.raises(RuntimeError, match="owned delivery release failed"):
        serve._launch(
            app,
            blocks,
            tmp_path,
            tmp_path,
            SimpleNamespace(
                release=lambda: None, release_deletion=lambda: None, writers=[]
            ),
        )
    assert model.held_release.is_set()


def test_runner_preserves_node_watchdog_when_app_exit_also_fails(
    modules, monkeypatch, tmp_path
):
    runner = modules[1]
    tribute = tmp_path / "input-tribute.js"
    tribute.write_bytes(b"owned")
    monkeypatch.setenv("MARA_BROWSER_TRIBUTE", str(tribute))
    monkeypatch.setattr(
        runner, "TRIBUTE_SHA256", runner.hashlib.sha256(b"owned").hexdigest()
    )
    monkeypatch.setattr(runner, "_record_source", lambda *args: None)
    primary = subprocess.TimeoutExpired(["owned-node"], 600)

    def launch(*args, **kwargs):
        (tmp_path / "attempt" / "ready.json").write_text("{}")
        return SimpleNamespace(
            poll=lambda: None, wait=fail_release, pid=12345, args=["owned-app"]
        )

    def node(*args, **kwargs):
        raise primary

    monkeypatch.setattr(runner.subprocess, "Popen", launch)
    monkeypatch.setattr(runner, "_run_node", node)
    with pytest.raises(subprocess.TimeoutExpired) as caught:
        runner.run(tmp_path / "attempt")
    assert caught.value is primary


def test_wait_exit_is_not_generator_completion(modules, tmp_path):
    model = SimpleNamespace(
        held_started=Event(),
        held_finished=Event(),
        held_release=Event(),
        generator_finished=Event(),
    )
    model.held_started.set()
    model.held_finished.set()
    modules[0]._release_model_boundary(model, tmp_path)
    state = json.loads((tmp_path / "model-gate-teardown.json").read_text())
    assert state["wait_exited"] is True
    assert state["generator_finished"] is False


def test_wait_exit_and_terminal_request_do_not_hide_live_generator(modules):
    exit_module = importlib.import_module("browser_fixture_exit")
    state: dict[str, Any] = {
        "active_jobs": [],
        "queued": [],
        "writers": [],
        "model_workers": {},
        "requests": {"owned": {"status": "success"}},
        "generators": {"held": {"finished": None}},
    }
    assert not exit_module.quiescent(state)
    state["generators"]["held"]["finished"] = 1
    assert exit_module.quiescent(state)
    state["active_jobs"] = ["later-worker"]
    assert not exit_module.quiescent(state)


def test_app_primary_survives_all_release_failures(modules, monkeypatch, tmp_path):
    serve = modules[0]
    app, blocks, model = launch_fixture(monkeypatch, serve, tmp_path)
    primary = AssertionError("original UI assertion")
    monkeypatch.setattr(serve, "_write_ready", lambda *args: None)
    monkeypatch.setattr(
        serve.time, "sleep", lambda seconds: (_ for _ in ()).throw(primary)
    )
    observer = SimpleNamespace(
        release=fail_release, release_deletion=fail_release, writers=[]
    )
    with pytest.raises(AssertionError) as caught:
        serve._launch(app, blocks, tmp_path, tmp_path, observer)
    assert caught.value is primary
    assert model.held_release.is_set()
    receipt = json.loads((tmp_path / "producer-teardown.json").read_text())
    assert [item["boundary"] for item in receipt["releases"]] == [
        "ui",
        "model",
        "embedding",
        "deletion_embedding",
    ]
    assert len(receipt["secondary"]) == 3
    assert receipt["quiescent"] is True


def test_node_watchdog_survives_forced_exit_failure(modules, monkeypatch, tmp_path):
    runner = modules[1]
    node = SimpleNamespace(
        pid=12345,
        poll=lambda: None,
        wait=lambda **kw: (_ for _ in ()).throw(
            subprocess.TimeoutExpired("node", kw["timeout"])
        ),
    )
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **kw: node)
    monkeypatch.setattr(runner, "_terminate_owned", fail_release)
    with pytest.raises(subprocess.TimeoutExpired):
        runner._run_node(tmp_path, {}, tmp_path, timeout=0)


def test_cleanup_does_not_unwind_stores_after_monitor_failure(
    modules, monkeypatch, tmp_path
):
    exit_module = importlib.import_module("browser_fixture_exit")
    serve = modules[0]
    _, blocks, model = launch_fixture(monkeypatch, serve, tmp_path)
    observer = SimpleNamespace(
        release=lambda: None, release_deletion=lambda: None, writers=[]
    )
    barriers = SimpleNamespace(release_all=lambda: None, status=lambda: {})
    monkeypatch.setattr(exit_module, "producer_state", fail_release)
    monkeypatch.setattr(
        exit_module.os, "_exit", lambda code: (_ for _ in ()).throw(SystemExit(code))
    )
    with pytest.raises(SystemExit) as caught:
        exit_module.finish_app(
            blocks,
            model,
            barriers,
            observer,
            tmp_path,
            AssertionError("primary"),
            timeout=0,
        )
    assert caught.value.code == 2
    assert json.loads((tmp_path / "cleanup.json").read_text())["removed"] is False


def test_real_gradio_disconnect_records_unstarted_request_removal(modules):
    import gradio
    from fastapi import Request
    from gradio.queueing import Event as QueueEvent
    from gradio.queueing import EventQueue, Queue

    assert gradio.__version__ == "4.39.0"
    exit_module = importlib.import_module("browser_fixture_exit")

    async def disconnect():
        queue = Queue(False, 1, 1, None, SimpleNamespace())
        fn = SimpleNamespace(concurrency_id="owned", _id=12)
        events = [
            QueueEvent(session, fn, Request({"type": "http"}), "owned-user")
            for session in ("disconnecting", "other-session")
        ]
        group = EventQueue("owned", 1)
        group.queue.extend(events)
        queue.event_queue_per_concurrency_id["owned"] = group
        for event in events:
            queue.event_analytics[event._id] = {
                "status": "queued",
                "session_hash": event.session_hash,
            }
        exit_module.observe_queue_cancellations(queue)
        await queue.clean_events(session_hash="disconnecting")
        return queue, group, events

    queue, group, events = asyncio.run(disconnect())
    assert group.queue == [events[1]]
    assert queue.event_analytics[events[0]._id]["status"] == "queued"
    cancellation = queue.owned_cancelled_queued_events
    assert set(cancellation) == {events[0]._id}
    assert cancellation[events[0]._id]["session_hash"] == "disconnecting"
    assert cancellation[events[0]._id]["fn"] == 12


@pytest.mark.parametrize(
    "evidence", ["exact", "missing", "wrong-session", "processing"]
)
def test_only_observed_exact_queued_cancellation_is_terminal(modules, evidence):
    exit_module = importlib.import_module("browser_fixture_exit")
    state: dict[str, Any] = {
        "active_jobs": [],
        "queued": [],
        "writers": [],
        "model_workers": {},
        "generators": {},
        "requests": {"owned": {"status": "queued", "session_hash": "session-a"}},
        "cancelled_queued_events": {"owned": {"session_hash": "session-a", "fn": 12}},
    }
    if evidence == "missing":
        state["cancelled_queued_events"] = {}
    elif evidence == "wrong-session":
        state["cancelled_queued_events"]["owned"]["session_hash"] = "session-b"
    elif evidence == "processing":
        state["requests"]["owned"]["status"] = "processing"
    assert exit_module.quiescent(state) is (evidence == "exact")
    state["active_jobs"] = ["owned"]
    assert not exit_module.quiescent(state)
