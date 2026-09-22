"""Failures in the owned browser fixture must not strand a later release."""

import importlib
import json
import subprocess
import sys
from pathlib import Path
from threading import Event
from types import SimpleNamespace

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
        held_started=Event(), held_finished=Event(), held_release=Event()
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
    monkeypatch.setattr(sut, "_selection_roles", lambda *args: {})
    monkeypatch.setattr(
        sut, "_write_ready", lambda *args: (output / "stop").write_text("stop")
    )
    barriers = SimpleNamespace(
        bind_delivery=lambda queue: None, release_all=fail_release
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
        _queue=object(),
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
        serve._launch(app, blocks, tmp_path, tmp_path, object())
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
        return SimpleNamespace(poll=lambda: None, wait=fail_release, pid=12345)

    def node(*args, **kwargs):
        raise primary

    monkeypatch.setattr(runner.subprocess, "Popen", launch)
    monkeypatch.setattr(runner.subprocess, "run", node)
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
