"""Run the real chat browser regressions and gracefully close owned resources."""

import argparse
import hashlib
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

TRIBUTE_URL = "https://cdnjs.cloudflare.com/ajax/libs/tributejs/5.1.3/tribute.min.js"
TRIBUTE_SHA256 = "40703cceb4b468e72ae1eda73afdebdff4acc184b76a047bdd8dd487dd837ae5"


def run(output):
    from pytest_runtime_isolation import start_process_test_runtime

    output.mkdir(parents=True, exist_ok=False)
    os.environ["MARA_DIAGNOSTIC_ISOLATION_REQUIRED"] = "1"
    runtime = start_process_test_runtime(evidence_dir=output)
    primary = None
    try:
        _isolation_receipt(runtime, output, "launcher")
        return _run(output)
    except BaseException as error:
        primary = error
        raise
    finally:
        _finish_runtime(runtime, output, primary)


def _finish_runtime(runtime, output, primary):
    try:
        journal = output / "processes.jsonl"
        records = (
            [json.loads(line) for line in journal.read_text().splitlines()]
            if journal.exists()
            else []
        )
        started = {row["pid"] for row in records if row["state"] == "started"}
        exited = {
            row["pid"]
            for row in records
            if row["state"] == "exited" and row["exit_code"] is not None
        }
        if started - exited:
            raise RuntimeError(
                "Retaining diagnostic root: owned process exit is unproved"
            )
        runtime.close()
    except Exception as error:
        (output / "launcher-cleanup-error.json").write_text(
            json.dumps(
                {
                    "primary": repr(primary),
                    "cleanup": repr(error),
                    "root": str(runtime.paths.root),
                }
            ),
            encoding="utf-8",
        )
        if primary is None:
            raise
    finally:
        (output / "launcher-cleanup.json").write_text(
            json.dumps(
                {
                    "root": str(runtime.paths.root),
                    "removed": not runtime.paths.root.exists(),
                }
            ),
            encoding="utf-8",
        )


def _isolation_receipt(runtime, output, role):
    from importlib.machinery import PathFinder

    guard = runtime.process_guard
    assert guard is not None
    guard.check_environment(os.environ)
    repository = Path(__file__).resolve().parents[2]
    modules = {}
    for name in ("ktem", "kotaemon", "slide_cli", "theflow", "gradio"):
        spec = PathFinder.find_spec(name)
        if spec is None or spec.origin is None:
            raise RuntimeError(f"Missing diagnostic package: {name}")
        source = Path(spec.origin).resolve()
        if name in {"ktem", "kotaemon", "slide_cli"} and not source.is_relative_to(
            repository
        ):
            raise RuntimeError(f"Unexpected diagnostic package source: {name}")
        modules[name] = str(source)
    (output / f"isolation-{role}.json").write_text(
        json.dumps(
            {
                "before_business_import": not any(
                    name in sys.modules for name in modules if name != "gradio"
                ),
                "pid": os.getpid(),
                "root": str(runtime.paths.root),
                "python": sys.executable,
                "prefix": sys.prefix,
                "cwd": os.getcwd(),
                "packages": modules,
                "paths": runtime.paths.environment(),
                "python_audit_guard": True,
                "native_os_sandbox": False,
            }
        ),
        encoding="utf-8",
    )


def _run(output):
    repository = Path(__file__).resolve().parents[2]
    if any((output / name).exists() for name in ("ready.json", "stop", "server.log")):
        raise ValueError("Use a fresh browser evidence directory")
    source = os.environ.get("MARA_BROWSER_TRIBUTE")
    if source:
        tribute = Path(source).read_bytes()
    else:
        with urlopen(TRIBUTE_URL, timeout=30) as response:
            tribute = response.read()
    assert hashlib.sha256(tribute).hexdigest() == TRIBUTE_SHA256
    (output / "tribute.min.js").write_bytes(tribute)
    _record_source(repository, output)
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        str(path)
        for path in (
            repository,
            repository / "libs/ktem",
            repository / "libs/kotaemon",
            repository / "libs/slide_cli",
        )
    )
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["MARA_BROWSER_PYTHON"] = sys.executable
    environment["NO_PROXY"] = "localhost,127.0.0.1,::1"
    environment.pop("NODE_OPTIONS", None)
    with (output / "server.log").open("w", encoding="utf-8") as log:
        server = subprocess.Popen(
            [
                sys.executable,
                "-B",
                str(repository / "tests/browser/serve_chat_submission.py"),
                "--output",
                str(output),
            ],
            cwd=environment["MARA_PYTEST_RUNTIME_ROOT"],
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=os.name != "nt",
        )
        primary: BaseException | None = None
        _process_record(
            output,
            "app",
            server,
            "started",
            command=server.args,
            cwd=environment["MARA_PYTEST_RUNTIME_ROOT"],
            source=str(output / "source.json"),
        )
        try:
            deadline = time.monotonic() + 120
            while not (output / "ready.json").exists():
                if server.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError(
                        f"Browser server did not become ready: {output / 'server.log'}"
                    )
                time.sleep(0.2)
            code = _run_node(repository, environment, output)
            if code:
                primary = RuntimeError(f"Owned Node exited {code}; see results.json")
            return code
        except BaseException as error:
            primary = error
            raise
        finally:
            _stop_server(server, output, primary)


def _process_record(output, role, process, state, **fields):
    with (output / "processes.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "at": datetime.now(timezone.utc).isoformat(),
                    "role": role,
                    "pid": process.pid,
                    "state": state,
                    **fields,
                }
            )
            + "\n"
        )


def _terminate_owned(process, output, role):
    if process.poll() is None:
        _process_record(output, role, process, "forced_termination")
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=True,
                capture_output=True,
            )
        else:
            import signal

            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)


def _run_node(repository, environment, output, *, timeout=600):
    command = [
        "node",
        str(repository / "tests/browser/chat_submission.cjs"),
        str(output),
    ]
    node = subprocess.Popen(
        command,
        cwd=environment["MARA_PYTEST_RUNTIME_ROOT"],
        env=environment,
        start_new_session=os.name != "nt",
    )
    _process_record(
        output,
        "node",
        node,
        "started",
        command=command,
        cwd=environment["MARA_PYTEST_RUNTIME_ROOT"],
        watchdog_seconds=timeout,
    )
    try:
        deadline = time.monotonic() + timeout
        while node.poll() is None:
            if time.monotonic() >= deadline or (output / "watchdog-node").exists():
                raise subprocess.TimeoutExpired(command, timeout)
            time.sleep(0.1)
        return node.returncode
    except subprocess.TimeoutExpired as primary:
        (output / "browser-stop").write_text("Node watchdog", encoding="utf-8")
        _process_record(output, "node", node, "watchdog", error=repr(primary))
        try:
            try:
                node.wait(timeout=15)
            except subprocess.TimeoutExpired:
                _terminate_owned(node, output, "node")
        except Exception as error:
            logging.exception("Owned Node shutdown failed after watchdog")
            (output / "node-stop-error.json").write_text(
                json.dumps({"primary": repr(primary), "cleanup": repr(error)}),
                encoding="utf-8",
            )
        raise primary
    finally:
        _process_record(output, "node", node, "exited", exit_code=node.poll())


def _stop_server(server, output, primary):
    try:
        (output / "stop").write_text("stop", encoding="utf-8")
        try:
            server.wait(timeout=45)
        except subprocess.TimeoutExpired:
            _terminate_owned(server, output, "app")
            raise
        if server.returncode != 0:
            raise RuntimeError(
                f"Browser server cleanup failed: {output / 'server.log'}"
            )
    except Exception as error:
        (output / "runner-cleanup-error.json").write_text(
            json.dumps({"primary": repr(primary), "cleanup": repr(error)}),
            encoding="utf-8",
        )
        if primary is None:
            raise
    finally:
        _process_record(output, "app", server, "exited", exit_code=server.poll())


BROWSER_INPUTS = [
    "pytest_runtime_isolation.py",
    "tests/test_runtime_process_guard.py",
    "tests/browser/serve_chat_submission.py",
    "tests/browser/chat_submission.cjs",
    "tests/browser/conversation_actions.cjs",
    "tests/browser/conversation_observer.cjs",
    "tests/browser/conversation_setup.cjs",
    "tests/browser/conversation_tails.cjs",
    "tests/browser/conversation_readiness.cjs",
    "tests/browser/conversation_reload.cjs",
    "tests/browser/conversation_contract.cjs",
    "tests/browser/conversation_contract.test.cjs",
    "tests/browser/conversation_readiness.test.cjs",
    "tests/browser/conversation_focus.test.cjs",
    "libs/ktem/ktem/assets/css/main.css",
    "libs/ktem/ktem/pages/chat/control.py",
    "tests/browser/file_browser_navigation.cjs",
    "tests/browser/file_browser_concurrency.cjs",
    "tests/browser/file_browser_barriers.py",
    "tests/browser/index_management.cjs",
    "tests/browser/group_operations.cjs",
    "libs/ktem/ktem/index/file/_events.py",
    "tests/browser/indexing_lifetime.cjs",
    "tests/browser/indexing_closeout.cjs",
    "tests/browser/indexing_lifetime_observer.py",
    "libs/kotaemon/kotaemon/artifact_pipeline.py",
    "libs/ktem/ktem/index/file/archive.py",
    "libs/ktem/ktem/index/file/pipelines.py",
    "libs/ktem/ktem/index/file/source_writes.py",
    "libs/ktem/ktem/index/file/index_materialization.py",
    "libs/ktem/ktem/index/file/deletion.py",
    "libs/kotaemon/kotaemon/indices/vectorindex.py",
    "libs/kotaemon/kotaemon/artifact_namespace.py",
    "libs/ktem/ktem/index/file/_indexing_service.py",
    "libs/ktem/ktem/docqa/_runtime_indexing.py",
    "tests/browser/studio_workflows.cjs",
    "tests/browser/studio_permissions.cjs",
    "libs/ktem/ktem/pages/chat/studio_callback_identity.py",
    "tests/browser/web_seam_observer.py",
    "tests/browser/web_operation_observer.py",
    "tests/browser/web_operation_observer.cjs",
    "tests/browser/gradio_refresh_observer.cjs",
    "tests/browser/gradio_frontend_evidence.py",
    "tests/browser/refresh_delivery_contract.cjs",
    "tests/browser/web_operation_observer.test.cjs",
    "tests/browser/refresh_delivery_contract.test.cjs",
    "libs/ktem/ktem_tests/file_browser_app_fixture.py",
    "libs/ktem/ktem_tests/chat_submission_model_fixture.py",
    "tests/browser/run_chat_submission.py",
    "tests/browser/browser_fixture_exit.py",
    "libs/ktem/ktem_tests/chat_submission_app_fixture.py",
    "libs/ktem/ktem/pages/chat/file_browser_updates.py",
    "libs/ktem/ktem/assets/js/file_browser_refresh.js",
    "libs/ktem/ktem/app.py",
    "libs/ktem/ktem/index/file/_selector_ui.py",
    "libs/ktem/ktem/index/file/_chat_upload_events.py",
    "libs/ktem/ktem/pages/chat/chat_layout.py",
    "libs/ktem/ktem/pages/chat/chat_knowledge_graph_bindings.py",
    "libs/ktem/ktem/pages/chat/__init__.py",
    "libs/ktem/ktem/index/file/ui.py",
    "libs/ktem/ktem/pages/chat/studio_note_actions.py",
    "libs/ktem/ktem/pages/chat/studio_artifact_controls.py",
    "libs/ktem/ktem/pages/chat/studio_artifact_generation.py",
    "libs/ktem/ktem/pages/chat/studio_artifact_mindmap.py",
    "libs/ktem/ktem/pages/chat/conversation_restore.py",
    "libs/ktem/ktem/pages/chat/chat_gradio_adapters.py",
    "libs/ktem/ktem/pages/chat/chat_conversation_events.py",
]


def _record_source(repository, output):
    names = list(BROWSER_INPUTS)
    names.extend(
        str(path.relative_to(repository))
        for path in (repository / "tests/browser").iterdir()
        if path.suffix in {".py", ".cjs"}
    )
    names.extend(
        str(asset.relative_to(repository))
        for asset in (repository / "libs/ktem/ktem/assets/js").glob("*.js")
    )
    (output / "source.json").write_text(
        json.dumps(
            {
                "head": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=repository, text=True
                ).strip(),
                "sha256": {
                    name: hashlib.sha256((repository / name).read_bytes()).hexdigest()
                    for name in names
                },
                "tribute_sha256": TRIBUTE_SHA256,
                "scenarios": os.environ.get("MARA_BROWSER_SCENARIOS", "all"),
                "public_fixture": os.environ.get("MARA_BROWSER_PUBLIC_FIXTURE") == "1",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    raise SystemExit(run(parser.parse_args().output.resolve()))
