"""Run the real chat browser regressions and gracefully close owned resources."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

TRIBUTE_URL = "https://cdnjs.cloudflare.com/ajax/libs/tributejs/5.1.3/tribute.min.js"
TRIBUTE_SHA256 = "40703cceb4b468e72ae1eda73afdebdff4acc184b76a047bdd8dd487dd837ae5"


def run(output):
    repository = Path(__file__).resolve().parents[2]
    output.mkdir(parents=True, exist_ok=True)
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
    with (output / "server.log").open("w", encoding="utf-8") as log:
        server = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "tests/browser/serve_chat_submission.py",
                "--output",
                str(output),
            ],
            cwd=repository,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 120
            while not (output / "ready.json").exists():
                if server.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError(
                        f"Browser server did not become ready: {output / 'server.log'}"
                    )
                time.sleep(0.2)
            completed = subprocess.run(
                ["node", "tests/browser/chat_submission.cjs", str(output)],
                cwd=repository,
                env=environment,
                timeout=600,
            )
            return completed.returncode
        finally:
            (output / "stop").write_text("stop", encoding="utf-8")
            server.wait(timeout=45)
            if server.returncode != 0:
                raise RuntimeError(
                    f"Browser server cleanup failed: {output / 'server.log'}"
                )


def _record_source(repository, output):
    names = [
        "tests/browser/serve_chat_submission.py",
        "tests/browser/chat_submission.cjs",
        "tests/browser/conversation_actions.cjs",
        "tests/browser/file_browser_navigation.cjs",
        "tests/browser/file_browser_concurrency.cjs",
        "tests/browser/file_browser_barriers.py",
        "tests/browser/index_management.cjs",
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
        "libs/ktem/ktem_tests/file_browser_app_fixture.py",
        "libs/ktem/ktem_tests/chat_submission_model_fixture.py",
        "tests/browser/run_chat_submission.py",
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
