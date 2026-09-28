"""Real installed MARA/MARA-cli apply against an ephemeral Windows Known Folder."""

import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from windows_apply_fixture import hosted_scope


def run_console(root, command, session, output, expected=0):
    executable = Path(sys.prefix) / "Scripts" / f"{command}.exe"
    argv = [str(executable), "apply", session, "--output", str(output), "--json"]
    completed = subprocess.run(
        argv,
        cwd=output.parent,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    label = f"{command}-{session}"
    (root / f"{label}.stdout").write_text(completed.stdout, encoding="utf-8")
    (root / f"{label}.stderr").write_text(completed.stderr, encoding="utf-8")
    assert completed.returncode == expected, (
        label,
        completed.returncode,
        completed.stderr,
    )
    return {
        "command": argv,
        "exit_code": completed.returncode,
        "payload": json.loads(completed.stdout) if expected == 0 else None,
    }


def installed_wheels():
    distributions = {}
    for name in ("kotaemon", "ktem", "mara-research-cli", "mara-app"):
        dist = importlib.metadata.distribution(name)
        metadata = dist.read_text("direct_url.json")
        assert metadata is not None
        direct = json.loads(metadata)
        assert "archive_info" in direct and not direct.get("dir_info", {}).get(
            "editable"
        )
        distributions[name] = {"version": dist.version, "wheel": direct}
    return distributions


def exercise(root):
    import psutil
    from pptx import Presentation
    from slide_cli import deck, paths
    from slide_cli.session_store import SlideSessionStore

    assert Path(deck.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
    assert paths.get_slide_runtime_paths().data_dir == root
    assert "PYTHONPATH" not in os.environ
    cwd = root / "fixture" / "outside 中文"
    cwd.mkdir(parents=True)
    source = cwd / "原始.pptx"
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[1])
    slide.shapes.title.text = "Owned original"
    slide.placeholders[1].text = "Owned body"
    presentation.save(source)
    original = source.read_bytes()
    snapshot = deck.load_deck_snapshot(source)
    shape, body = snapshot.slides[0].shapes[:2]
    patch = deck.DeckPatch(
        "Owned patch",
        [
            deck.TextReplaceOp(1, shape.target_id, shape.text, "Owned edited"),
            deck.TextReplaceOp(1, body.target_id, "stale value", "Must not apply"),
        ],
    )
    store = SlideSessionStore()
    receipts = []
    for index, command in enumerate(("MARA", "MARA-cli")):
        session = store.create_session(
            mode="run",
            input_path=str(source),
            cwd=str(cwd),
            session_id=f"owned-{index}",
        )
        store.append_event(
            session.session_id, {"kind": "final", "patch": patch.as_dict()}
        )
        output = cwd / f"修改后-{index}.pptx"
        receipt = run_console(root, command, session.session_id, output)
        payload = receipt["payload"]
        assert payload["applied_count"] == 1 and payload["skipped_count"] == 1
        assert payload["session_id"] == session.session_id
        reloaded = deck.load_deck_snapshot(output)
        assert reloaded.slides[0].shapes[0].text == "Owned edited"
        assert reloaded.slides[0].shapes[1].text == "Owned body"
        saved = store.load_session(session.session_id)
        assert saved is not None
        assert saved.status == "completed" and saved.output_path == str(output)
        assert [event["kind"] for event in saved.events] == ["final", "apply"]
        assert source.read_bytes() == original
        receipts.append(receipt)
    missing = cwd / "missing-result.pptx"
    receipts.append(run_console(root, "MARA", "not-a-session", missing, expected=1))
    assert not missing.exists() and source.read_bytes() == original
    assert not list(cwd.glob(".mara-deck-*"))
    guards = [json.loads(p.read_text()) for p in root.glob("console-guard-*.json")]
    assert len(guards) == 3 and all(record["closed"] for record in guards)
    assert all(not psutil.pid_exists(record["pid"]) for record in guards)
    return {
        "commands": receipts,
        "default_paths": True,
        "cwd": str(cwd),
        "source_sha256": hashlib.sha256(original).hexdigest(),
        "module_path": deck.__file__,
        "version": importlib.metadata.version("mara-research-cli"),
        "installed_wheels": installed_wheels(),
        "console_processes": guards,
    }


def verify():
    root, identity = hosted_scope()
    if root.exists():
        raise RuntimeError("Default MARA scope already exists; refusing reuse")
    # The actual Known Folder was resolved and approved before this first write.
    root.mkdir(parents=True)
    os.environ["MARA_DIAGNOSTIC_ISOLATION_REQUIRED"] = "1"
    from pytest_runtime_isolation import start_process_test_runtime

    runtime = start_process_test_runtime(evidence_dir=root)
    authorization = {
        **identity,
        "root": str(root),
        "sha": os.environ["GITHUB_SHA"],
        "run": os.environ["GITHUB_RUN_ID"],
        "owner": runtime.owner_token,
        "fresh_before_write": True,
    }
    (root / "authorization.json").write_text(json.dumps(authorization, indent=2))
    print(json.dumps({"authorized_scope": str(root)}), flush=True)
    os.environ["MARA_CI_DEFAULT_APPLY_CHILD"] = "1"
    try:
        result = exercise(root)
        assert runtime.process_guard is not None
        assert not runtime.process_guard.denials
        (root / "result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    finally:
        runtime.close()
        (root / "cleanup.json").write_text(
            json.dumps({"runtime_removed": not runtime.paths.root.exists()})
        )


def collect(destination):
    root, _ = hosted_scope()
    authorization = json.loads((root / "authorization.json").read_text())
    if (
        root != root.resolve()
        or authorization["root"] != str(root)
        or authorization["sha"] != os.environ["GITHUB_SHA"]
        or (root / ".mara-pytest-owner").read_text() != authorization["owner"]
    ):
        raise RuntimeError("Refusing cleanup of an unowned default MARA scope")
    destination = Path(destination).resolve()
    runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve()
    if not destination.is_relative_to(runner_temp) or destination.exists():
        raise RuntimeError("Evidence destination must be fresh and within RUNNER_TEMP")
    shutil.copytree(root, destination)
    # The producer process has exited before this separate collect invocation.
    shutil.rmtree(root)
    (destination / "scope-cleanup.json").write_text(
        json.dumps({"default_scope_removed": not root.exists()})
    )


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--collect":
        collect(sys.argv[2])
    elif len(sys.argv) == 1:
        verify()
    else:
        raise SystemExit("Expected no arguments, or --collect DESTINATION")
